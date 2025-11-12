#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Индикатор состояния «Движение/Покой» для Promobot M Edu через UART.

Функции:
- Подписка на состояния суставов (J1..J3) через pm_python_sdk.
- Детект движения по скоростям (если есть) или по производной углов.
- UART-команды для LED-модуля: "BLINK 2\n" при движении, "OFF\n" при покое.
- Реакция < 0.2 с за счёт вызова из колбэка.
- Безопасная демо-траектория: поворот основания слева-направо и обратно.

Зависимости:
  pip install pyserial
  pip install /path/to/pm_python_sdk-0.6.6.tar.gz

Пример запуска:
  python led_motion_indicator.py --host 192.168.1.42 --client-id demo \
      --login user --password pass --uart /dev/serial0 --demo
"""
from __future__ import annotations
import time
import json
import math
import signal
import argparse
import threading
from typing import Dict, Optional

import serial  # pyserial
from sdk.manipulators.medu import MEdu  # из pm_python_sdk


class UARTLed:
    """Мини-драйвер UART-LED. Говорим модулю: BLINK <hz> / OFF."""
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, timeout: float = 0.05):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._last_mode = None
        self._lock = threading.Lock()

    def _send(self, msg: str) -> None:
        with self._lock:
            if not self.ser.is_open:
                self.ser.open()
            self.ser.write(msg.encode("ascii"))
            self.ser.flush()

    def blink(self, hz: float = 2.0) -> None:
        mode = f"BLINK {hz:.3g}\n"
        if self._last_mode != mode:
            self._send(mode)
            self._last_mode = mode

    def off(self) -> None:
        mode = "OFF\n"
        if self._last_mode != mode:
            self._send(mode)
            self._last_mode = mode

    def close(self) -> None:
        try:
            self.off()
        finally:
            try:
                self.ser.close()
            except Exception:
                pass


class MotionWatcher:
    """
    Отслеживает движение по данным joint-state.
    'moving' = True, если есть скорости > vel_thresh,
    либо если |Δугол|/Δt > vel_thresh (оценка скорости).
    """
    def __init__(self, vel_thresh: float = 0.01):
        self.vel_thresh = float(vel_thresh)  # рад/с
        self.last_t: Optional[float] = None
        self.last_pos: Optional[Dict[str, float]] = None
        self.moving = False
        self._lock = threading.Lock()

    def _compute_speed_mag(self, p_prev: Dict[str, float], p_now: Dict[str, float], dt: float) -> float:
        mags = []
        for j in p_now:
            if j in p_prev:
                dv = abs((p_now[j] - p_prev[j]) / max(dt, 1e-6))
                mags.append(dv)
        return max(mags) if mags else 0.0

    def on_joint_state(self, data: Dict) -> bool:
        """
        Колбэк для MEdu.subscribe_to_joint_state.
        Ожидаемый формат data:
          {"positions": {"povorot_osnovaniya": float, "privod_plecha": float, "privod_strely": float},
           "velocities": {"povorot_osnovaniya": float, "privod_plecha": float, "privod_strely": float}}
        Но обрабатываем и другие разумные варианты.
        Возвращает новое состояние moving.
        """
        try:
            # Универсальный разбор
            if "positions" in data and isinstance(data["positions"], dict):
                positions = {k: float(v) for k, v in data["positions"].items()}
            else:
                # fallback: плоский словарь углов
                positions = {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}

            velocities = {}
            if "velocities" in data and isinstance(data["velocities"], dict):
                velocities = {k: float(v) for k, v in data["velocities"].items()}

            t_now = time.monotonic()
            moving_detected = False

            # 1) Если есть скорости, используем их
            if velocities:
                moving_detected = any(abs(v) > self.vel_thresh for v in velocities.values())
            # 2) Иначе оцениваем производную по углам
            else:
                if self.last_t is not None and self.last_pos is not None:
                    dt = t_now - self.last_t
                    if dt > 0:
                        vmax = self._compute_speed_mag(self.last_pos, positions, dt)
                        moving_detected = vmax > self.vel_thresh

            # Обновить last-данные
            self.last_t = t_now
            self.last_pos = positions

            with self._lock:
                self.moving = moving_detected
            return moving_detected
        except Exception:
            return self.moving

    def is_moving(self) -> bool:
        with self._lock:
            return self.moving


def safe_demo(manip: MEdu) -> None:
    """
    Безопасная демонстрация: база к левому краю, затем к правому, затем в центр.
    Параметры подобраны мягкие (0.2), чтобы избежать рывков и случайных контактов.
    Перед запуском УБЕДИСЬ, что в радиусе ≥1 м от основания нет предметов.  # см. руководство
    """
    manip.get_control()
    # Базовая «высокая» поза: плечо и стрела в средних значениях.
    manip.move_to_angles(0.0, 0.40, 1.00, velocity_factor=0.20, acceleration_factor=0.20)
    # Левое крайнее (не абсолютный предел)
    manip.move_to_angles(-2.40, 0.40, 1.00, velocity_factor=0.20, acceleration_factor=0.20)
    # Правое крайнее (не абсолютный предел)
    manip.move_to_angles( 2.40, 0.40, 1.00, velocity_factor=0.20, acceleration_factor=0.20)
    # Возврат в центр
    manip.move_to_angles(0.0, 0.40, 1.00, velocity_factor=0.20, acceleration_factor=0.20)


def main():
    ap = argparse.ArgumentParser(description="LED-индикатор движения M Edu через UART")
    ap.add_argument("--host", required=True, help="IP адрес манипулятора (MQTT брокер)")
    ap.add_argument("--client-id", default="motion-led", help="Клиент ID")
    ap.add_argument("--login", default="user", help="Логин MQTT")
    ap.add_argument("--password", default="pass", help="Пароль MQTT")
    ap.add_argument("--uart", default="/dev/serial0", help="UART-порт (например, /dev/serial0 или /dev/ttyAMA0)")
    ap.add_argument("--baud", type=int, default=115200, help="Скорость UART, бод")
    ap.add_argument("--vel-thresh", type=float, default=0.01, help="Порог скорости, рад/с")
    ap.add_argument("--demo", action="store_true", help="Запустить демонстрационное движение")
    args = ap.parse_args()

    led = UARTLed(port=args.uart, baud=args.baud)
    manip = MEdu(args.host, args.client_id, args.login, args.password)

    stop_flag = {"stop": False}

    def handle_sigint(sig, frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    print("[INFO] Подключение к манипулятору…")
    manip.connect()

    watcher = MotionWatcher(vel_thresh=args.vel_thresh)

    def joint_callback(data: Dict):
        moving = watcher.on_joint_state(data)
        # Мгновенно обновить LED по изменению состояния
        if moving:
            led.blink(2.0)   # режим «Движение»: 2 Гц
        else:
            led.off()        # режим «Покой»: выключен

    manip.subscribe_to_joint_state(joint_callback)
    print("[OK] Подписка на состояние суставов активна. Индикатор готов.")

    try:
        if args.demo:
            print("[DEMO] Старт безопасной демонстрации (лево → право → центр)…")
            safe_demo(manip)
            print("[DEMO] Демонстрация завершена.")
        # Основной цикл ничего не делает — работаем по колбэку, но держим процесс живым.
        while not stop_flag["stop"]:
            time.sleep(0.1)
    finally:
        print("\n[CLEANUP] Выключаем LED и снимаем подписку…")
        try:
            manip.unsubscribe_from_joint_state()
        except Exception:
            pass
        led.close()


if __name__ == "__main__":
    main()
