#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostics.py — тестовый стенд для Promobot M Edu и учебных скриптов.

Проверяет:
  1) Импорт SDK и подключение к манипулятору.
  2) Чтение суставов и небольшой шаг по суставам.
  3) Движение по J1 через SpeedGuard (task_1).
  4) Подписку на состояние суставов (task_2).
  5) UART-LED: открытие порта, команды BLINK/OFF (task_2-подобно).
  6) Чтение текущих декартовых координат (write_coords.safe_get_pose).
  7) Проигрывание первой сохранённой точки из coords3.json (task_3).
  8) Вращение захвата (rotate_gripper из task_3).

Запуск:
    python diagnostics.py --host 172.16.2.190 --uart /dev/serial0

Перед любыми движениями:
    ► Убедись, что вокруг манипулятора НЕТ предметов в радиусе ≥ 1 м.
"""

from __future__ import annotations
import argparse
import time
import sys
from typing import Dict

import serial  # pyserial

from sdk.manipulators.medu import MEdu

# импорт учебных файлов
from task_1 import SpeedGuard, rad2deg
from task_2 import MotionWatcher  # UARTLed из task_2 не импортируем, делаем локальный мини-драйвер
from task_3 import (
    COORDS_FILE,
    VELOCITY_SCALE,
    ACCEL_SCALE,
    PLANNER,
    pose_to_params,
    rotate_gripper,
)
from write_coords import safe_get_pose


# -------- Мини-драйвер UART-LED (аналогично task_2.UARTLed) --------

class UARTLed:
    """Простейший драйвер для теста UART-LED: BLINK <hz> и OFF."""
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, timeout: float = 0.05):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._last_mode = None

    def _send(self, msg: str) -> None:
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
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass


# -------- Обёртки над тестами --------

def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"{title}")
    print("=" * 70)


def test_1_connect(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 1 — Подключение к манипулятору")
    try:
        m = MEdu(host, client_id, login, password)
        print("[*] Создан объект MEdu.")
        m.connect()
        print("[+] Подключение успешно.")
        m.disconnect()
        print("[+] Отключение успешно.")
        print("[OK] Тест 1 ПРОЙДЕН.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка при подключении: {e}")
        return False


def test_2_small_joint_move(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 2 — Чтение суставов и небольшой шаг")
    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")
        m.get_control()
        print("[+] Управление получено.")

        joints = m.get_joint_angles()
        print(f"[*] Текущие углы (рад): {joints}")

        # Делаем небольшой шаг по J1 (около 0.1 рад), остальные суставы не трогаем
        j1 = joints[0]
        target_j1 = j1 + 0.1
        print(f"[*] Двигаем J1 на +0.1 рад: {j1:.3f} -> {target_j1:.3f}")
        m.move_to_angles(target_j1, joints[1], joints[2],
                         velocity_factor=0.1, acceleration_factor=0.1)

        joints2 = m.get_joint_angles()
        print(f"[+] Новые углы (рад): {joints2}")
        print("[OK] Тест 2 ПРОЙДЕН.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка в тесте 2: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


def test_3_speed_guard(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 3 — SpeedGuard (динамическое ограничение скорости по зонам J1)")
    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")
        m.get_control()
        print("[+] Управление получено.")

        # Безопасные значения для J2/J3 (как в примерах)
        SAFE_J2 = 0.40
        SAFE_J3 = 1.00

        joints = m.get_joint_angles()
        j1_now_deg = rad2deg(joints[0])
        print(f"[*] Текущий J1: {j1_now_deg:.1f}°")

        # Сделаем тестовый ход на +30° (с учётом границ)
        target_deg = max(min(j1_now_deg + 30.0, 160.0), -160.0)
        print(f"[*] Цель для теста SpeedGuard: {target_deg:.1f}°")

        guard = SpeedGuard(m, SAFE_J2, SAFE_J3)
        guard.move_j1_guarded(target_deg)
        print("[+] Перемещение через SpeedGuard завершено.")
        print("[OK] Тест 3 ПРОЙДЕН.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка в тесте 3: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


def test_4_joint_subscription(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 4 — Подписка на состояния суставов (без движения)")
    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")

        watcher = MotionWatcher(vel_thresh=0.01)
        recv: Dict[str, int] = {"count": 0}

        def cb(data: Dict):
            recv["count"] += 1
            watcher.on_joint_state(data)

        m.subscribe_to_joint_state(cb)
        print("[*] Подписка активна. Ждём данные 2 секунды...")
        time.sleep(2.0)
        m.unsubscribe_from_joint_state()
        print("[*] Подписка снята.")

        if recv["count"] > 0:
            print(f"[+] Получено сообщений: {recv['count']}")
            print("[OK] Тест 4 ПРОЙДЕН.")
            return True
        else:
            print("[FAIL] Колбэк ни разу не вызвался — нет данных о суставах.")
            return False
    except Exception as e:
        print(f"[FAIL] Ошибка в тесте 4: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


def test_5_uart_led(uart_port: str, baud: int) -> bool:
    banner("ТЕСТ 5 — UART-LED (открытие порта и команды BLINK/OFF)")
    led = None
    try:
        led = UARTLed(port=uart_port, baud=baud)
        print(f"[+] Открыт UART-порт {uart_port} @ {baud} бод.")
        print("[*] Отправляем команду BLINK 2 Гц на 3 секунды...")
        led.blink(2.0)
        time.sleep(3.0)
        print("[*] Отправляем OFF...")
        led.off()
        print("[OK] Тест 5 ПРОЙДЕН (ошибок при работе с UART не было).")
        print("    ► Визуально проверь, что светодиод мигал и погас.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка работы с UART/LED: {e}")
        return False
    finally:
        if led is not None:
            led.close()


def test_6_read_cartesian(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 6 — Чтение декартовых координат TCP (safe_get_pose)")
    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")
        pose = safe_get_pose(m, timeout_seconds=5.0)
        print("[+] Получены координаты TCP:")
        print(pose)
        print("[OK] Тест 6 ПРОЙДЕН.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка при чтении декартовых координат: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


def test_7_play_first_point(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 7 — Движение к первой точке из coords3.json (task_3)")
    if not COORDS_FILE.exists():
        print(f"[FAIL] Файл с точками не найден: {COORDS_FILE.resolve()}")
        return False

    try:
        data = COORDS_FILE.read_text(encoding="utf-8")
        saved = __import__("json").loads(data)
        if not isinstance(saved, dict) or not saved:
            print(f"[FAIL] В {COORDS_FILE} нет валидных точек.")
            return False
    except Exception as e:
        print(f"[FAIL] Не удалось прочитать {COORDS_FILE}: {e}")
        return False

    # Берём первую точку по порядку
    name, pose = next(iter(saved.items()))
    print(f"[*] Первая точка: «{name}» из файла {COORDS_FILE}")

    try:
        pos, ori = pose_to_params(pose)
    except Exception as e:
        print(f"[FAIL] Неподдерживаемый формат позы «{name}»: {e}")
        return False

    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")
        m.get_control()
        print("[+] Управление получено.")
        print("ВНИМАНИЕ! Манипулятор поедет к сохранённой точке.")
        print("Убедись, что вокруг нет препятствий. Старт через 3 секунды...")
        time.sleep(3.0)

        m.move_to_coordinates(
            pos,
            ori,
            VELOCITY_SCALE,
            ACCEL_SCALE,
            PLANNER,
            timeout_seconds=60.0,
            throw_error=True,
        )
        print(f"[+] Достигнута точка «{name}».")
        print("[OK] Тест 7 ПРОЙДЕН.")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка при движении к «{name}»: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


def test_8_rotate_gripper(host: str, client_id: str, login: str, password: str) -> bool:
    banner("ТЕСТ 8 — Вращение захвата (rotate_gripper из task_3)")
    m = MEdu(host, client_id, login, password)
    try:
        m.connect()
        print("[+] Подключено.")
        m.get_control()
        print("[+] Управление получено.")
        print("ВНИМАНИЕ! Захват должен быть подключён через поворотный модуль.")
        print("Вращаем на +45°, затем -45°...")
        time.sleep(2.0)

        rotate_gripper(m, angle_deg=45, power_on=True, power_off_after=False)
        time.sleep(1.0)
        rotate_gripper(m, angle_deg=-45, power_on=True, power_off_after=True)
        print("[OK] Тест 8 ПРОЙДЕН (команды к захвату отправлены).")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка при вращении захвата: {e}")
        return False
    finally:
        try:
            m.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


# -------- Главное меню --------

def main() -> None:
    parser = argparse.ArgumentParser(description="Диагностический стенд для Promobot M Edu")
    parser.add_argument("--host", default="172.16.2.190", help="IP адрес манипулятора (MQTT брокер)")
    parser.add_argument("--client-id", default="diag-tool", help="MQTT client-id")
    parser.add_argument("--login", default="user", help="Логин MQTT")
    parser.add_argument("--password", default="pass", help="Пароль MQTT")
    parser.add_argument("--uart", default="/dev/serial0", help="UART-порт для LED")
    parser.add_argument("--baud", type=int, default=115200, help="Скорость UART, бод")
    args = parser.parse_args()

    tests = {
        "1": ("Подключение к манипулятору", lambda: test_1_connect(args.host, args.client_id, args.login, args.password)),
        "2": ("Небольшое движение по суставам", lambda: test_2_small_joint_move(args.host, args.client_id, args.login, args.password)),
        "3": ("SpeedGuard по J1 (зоны скорости)", lambda: test_3_speed_guard(args.host, args.client_id, args.login, args.password)),
        "4": ("Подписка на состояния суставов", lambda: test_4_joint_subscription(args.host, args.client_id, args.login, args.password)),
        "5": ("UART-LED BLINK/OFF", lambda: test_5_uart_led(args.uart, args.baud)),
        "6": ("Чтение декартовых координат TCP", lambda: test_6_read_cartesian(args.host, args.client_id, args.login, args.password)),
        "7": ("Движение к первой точке из coords3.json", lambda: test_7_play_first_point(args.host, args.client_id, args.login, args.password)),
        "8": ("Вращение захвата", lambda: test_8_rotate_gripper(args.host, args.client_id, args.login, args.password)),
    }

    while True:
        print("\n" + "-" * 70)
        print("ДИАГНОСТИЧЕСКИЕ ТЕСТЫ M EDU")
        print("Параметры подключения:")
        print(f"  host={args.host}, client_id={args.client_id}, login={args.login}, uart={args.uart}")
        print("-" * 70)
        for k, (name, _) in tests.items():
            print(f"  {k}. {name}")
        print("  a. Запустить ВСЕ тесты по очереди")
        print("  q. Выход")
        choice = input("\nВыберите пункт меню: ").strip().lower()

        if choice == "q":
            print("Выход.")
            break
        elif choice == "a":
            results = {}
            for k, (name, fn) in tests.items():
                ok = fn()
                results[k] = ok
            print("\nРЕЗЮМЕ:")
            for k, (name, _) in tests.items():
                status = "OK" if results.get(k) else "FAIL"
                print(f"  [{status}] {k}. {name}")
        elif choice in tests:
            _, fn = tests[choice]
            fn()
        else:
            print("Неизвестный пункт меню.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        sys.exit(1)
