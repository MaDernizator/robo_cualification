"""
Индикатор движения манипулятора Promobot M Edu через GPIO.
Если рука движется — светодиод моргает с частотой 2 Гц.
Если покой — светодиод выключен.
"""

import time
import signal
import threading
from typing import Dict, Optional

from sdk.manipulators.medu import MEdu

# --- Настройки ---
HOST = "10.5.0.2"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "cells-calib-001"
GPIO_LED_PATH = "/dev/gpiochip4/e1_pin"
VELOCITY_THRESHOLD = 0.01  # Порог скорости в рад/с для определения движения

# --- Константы для мигания светодиода ---
BLINK_FREQUENCY_HZ = 2  # Частота мигания 2 Гц
BLINK_HALF_PERIOD = 0.25  # Половина периода (0.5 с / 2 = 0.25 с вкл/выкл)


class GpioLedController:
    """Контроллер управления светодиодом через GPIO"""

    def __init__(self, manipulator: MEdu, gpio_path: str):
        self.manipulator = manipulator
        self.gpio_path = gpio_path
        self._is_blinking = False
        self._blink_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _blink_loop(self):
        """Цикл мигания светодиода в отдельном потоке"""
        try:
            while not self._stop_event.is_set():
                # Включаем светодиод
                self.manipulator.write_gpio(self.gpio_path, 1)
                if self._stop_event.wait(timeout=BLINK_HALF_PERIOD):
                    break

                # Выключаем светодиод
                self.manipulator.write_gpio(self.gpio_path, 0)
                if self._stop_event.wait(timeout=BLINK_HALF_PERIOD):
                    break
        except Exception:
            pass
        finally:
            # Гарантируем выключение светодиода при выходе
            try:
                self.manipulator.write_gpio(self.gpio_path, 0)
            except Exception:
                pass

    def start_blinking(self):
        """Запуск мигания светодиода"""
        if self._is_blinking:
            return

        self._stop_event.clear()
        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()
        self._is_blinking = True

    def stop_blinking(self):
        """Остановка мигания светодиода"""
        if not self._is_blinking:
            return

        self._stop_event.set()
        if self._blink_thread:
            self._blink_thread.join(timeout=0.3)

        self._is_blinking = False

        # Выключаем светодиод
        try:
            self.manipulator.write_gpio(self.gpio_path, 0)
        except Exception:
            pass


class MotionWatcher:
    """Наблюдатель за движением манипулятора"""

    def __init__(self, velocity_threshold: float):
        self.velocity_threshold = velocity_threshold
        self.last_timestamp: Optional[float] = None
        self.last_positions: Optional[Dict[str, float]] = None
        self.is_moving_flag = False
        self._lock = threading.Lock()

    def _compute_max_joint_speed(
            self,
            positions_previous: Dict[str, float],
            positions_current: Dict[str, float],
            time_delta: float
    ) -> float:
        """Вычисление максимальной скорости среди всех суставов"""
        joint_speeds = []

        for joint_name in positions_current:
            if joint_name in positions_previous:
                # Вычисляем скорость как изменение позиции за время
                speed = abs((positions_current[joint_name] - positions_previous[joint_name]) / max(time_delta, 1e-6))
                joint_speeds.append(speed)

        return max(joint_speeds) if joint_speeds else 0.0

    def on_joint_state(self, joint_data: Dict) -> bool:
        """
        Обработка данных о состоянии суставов.
        Возвращает True, если обнаружено движение.
        """
        try:
            # Извлекаем позиции суставов
            if "positions" in joint_data and isinstance(joint_data["positions"], dict):
                current_positions = {key: float(value) for key, value in joint_data["positions"].items()}
            else:
                current_positions = {key: float(value) for key, value in joint_data.items() if
                                     isinstance(value, (int, float))}

            # Извлекаем скорости суставов (если есть)
            current_velocities = {}
            if "velocities" in joint_data and isinstance(joint_data["velocities"], dict):
                current_velocities = {key: float(value) for key, value in joint_data["velocities"].items()}

            current_time = time.monotonic()
            movement_detected = False

            # Способ 1: используем скорости, если они доступны
            if current_velocities:
                movement_detected = any(
                    abs(velocity) > self.velocity_threshold for velocity in current_velocities.values())

            # Способ 2: вычисляем скорость по изменению позиций
            else:
                if self.last_timestamp is not None and self.last_positions is not None:
                    time_delta = current_time - self.last_timestamp
                    if time_delta > 0:
                        max_speed = self._compute_max_joint_speed(self.last_positions, current_positions, time_delta)
                        movement_detected = max_speed > self.velocity_threshold

            # Обновляем последние известные значения
            self.last_timestamp = current_time
            self.last_positions = current_positions

            # Потокобезопасное обновление флага движения
            with self._lock:
                self.is_moving_flag = movement_detected

            return movement_detected

        except Exception:
            return self.is_moving_flag

    def is_moving(self) -> bool:
        """Проверка, движется ли манипулятор в данный момент"""
        with self._lock:
            return self.is_moving_flag


def main():
    stop_requested = {"stop": False}

    def handle_sigint(signal_number, frame):
        """Обработчик сигнала прерывания (Ctrl+C)"""
        stop_requested["stop"] = True

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    print("[INFO] Создание подключения к манипулятору...")
    manipulator = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    led_controller = GpioLedController(manipulator, GPIO_LED_PATH)

    print("[INFO] Подключение...")
    manipulator.connect()

    motion_watcher = MotionWatcher(VELOCITY_THRESHOLD)

    def joint_state_callback(joint_data: Dict):
        """Callback для обработки данных о состоянии суставов"""
        is_moving = motion_watcher.on_joint_state(joint_data)
        if is_moving:
            led_controller.start_blinking()
        else:
            led_controller.stop_blinking()

    manipulator.subscribe_to_joint_state(joint_state_callback)

    print("[OK] Индикатор движения запущен. Нажмите Ctrl+C для остановки.")

    try:
        while not stop_requested["stop"]:
            time.sleep(0.1)
    finally:
        print("\n[CLEANUP] Выключение LED...")
        led_controller.stop_blinking()
        try:
            manipulator.unsubscribe_from_joint_state()
        except Exception:
            pass


if __name__ == "__main__":
    main()