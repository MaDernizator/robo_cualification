"""
conveyor_tests.py — тесты для конвейерной ленты (MGbot)

1) Установи SDK и убедись, что импорт:
       from sdk.manipulators.medu import MEdu
   работает в твоём окружении.

2) Заполни настройки подключения HOST / CLIENT_ID / LOGIN / PASSWORD
   под свой манипулятор.

3) В блоке if __name__ == "__main__": раскомментируй нужный тест:
   например, test_conveyor_speed(manipulator, interactive=True)

4) Запусти:
       python conveyor_tests.py
"""

import json
import time
from typing import Any, Dict, Optional

from sdk.manipulators.medu import MEdu


# ================== НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ==================

# ЗАМЕНИ эти значения на реальные для своего манипулятора
HOST = "192.168.88.182"   # IP манипулятора
CLIENT_ID = "122"         # ID клиента
LOGIN = "13"              # Логин
PASSWORD = "14"           # Пароль


# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def create_manipulator() -> MEdu:
    """
    Создаёт объект MEdu, подключается и захватывает управление.
    Выбросит исключение при ошибке подключения.
    """
    print(f"Подключение к манипулятору {HOST} (client_id={CLIENT_ID})...")
    manipulator = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    manipulator.connect()
    manipulator.get_control()
    print("Управление захвачено успешно.")

    # Лёгкая проверка наличия конвейера
    if not hasattr(manipulator, "mgbot_conveyer"):
        print("Внимание: у объекта нет атрибута 'mgbot_conveyer'. "
              "Проверь версию SDK и подключение конвейера USB.")
    else:
        print("Объект конвейера доступен: manipulator.mgbot_conveyer")

    return manipulator


def _clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(max_val, value))


def ask_int(prompt: str, default: int) -> int:
    """
    Удобный ввод целого числа с значением по умолчанию.
    Пустой ввод -> default.
    """
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Неверный формат, использую значение по умолчанию.")
        return default


def ask_float(prompt: str, default: float) -> float:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        print("Неверный формат, использую значение по умолчанию.")
        return default


def ask_str(prompt: str, default: str = "") -> str:
    raw = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    return raw or default


def require_conveyor(manipulator: MEdu):
    if not hasattr(manipulator, "mgbot_conveyer"):
        raise RuntimeError(
            "У манипулятора нет атрибута 'mgbot_conveyer'. "
            "Проверь подключение конвейера и версию SDK."
        )


# ================== ТЕСТЫ КОНВЕЙЕРНОЙ ЛЕНТЫ ==================

def test_conveyor_speed(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: вращение конвейера с заданной скоростью.

    Параметры:
        interactive: если True — просит ввести скорость с клавиатуры,
                     иначе использует значения по умолчанию.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ СКОРОСТИ КОНВЕЙЕРА ===")
    default_speed = 30  # безопасное значение по умолчанию

    if interactive:
        speed = ask_int("Введите скорость мотора (0..100)", default_speed)
    else:
        speed = default_speed

    speed = _clamp(speed, 0, 100)
    print(f"Устанавливаю скорость {speed}...")
    conveyor.set_speed_motors(speed)

    if speed > 0:
        run_time = ask_float("Время работы конвейера, секунд", 3.0) if interactive else 3.0
        print(f"Конвейер будет работать ~{run_time} секунд...")
        time.sleep(run_time)
        print("Останавливаю конвейер (скорость 0)...")
        conveyor.set_speed_motors(0)
    else:
        print("Скорость 0 — конвейер остановлен.")


def test_conveyor_servo_angle(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: поворот сервопривода, установленного на конвейере.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ СЕРВОПРИВОДА НА КОНВЕЙЕРЕ ===")
    default_angle = 45

    if interactive:
        angle = ask_int("Введите угол сервопривода (в градусах)", default_angle)
    else:
        angle = default_angle

    print(f"Устанавливаю угол сервопривода: {angle}°")
    conveyor.set_servo_angle(angle)
    time.sleep(1.0)
    print("Готово.")


def test_conveyor_led_color(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: установка цвета светодиода на конвейере.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ СВЕТОДИОДА КОНВЕЙЕРА ===")
    default_r, default_g, default_b = 255, 0, 0  # красный

    if interactive:
        r = ask_int("Введите компоненту R (0..255)", default_r)
        g = ask_int("Введите компоненту G (0..255)", default_g)
        b = ask_int("Введите компоненту B (0..255)", default_b)
    else:
        r, g, b = default_r, default_g, default_b

    r = _clamp(r, 0, 255)
    g = _clamp(g, 0, 255)
    b = _clamp(b, 0, 255)

    print(f"Устанавливаю цвет светодиода: R={r}, G={g}, B={b}")
    conveyor.set_led_color(r, g, b)
    time.sleep(0.5)
    print("Готово.")


def test_conveyor_display_text(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: вывод текста на дисплей конвейера.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ ДИСПЛЕЯ КОНВЕЙЕРА ===")
    default_text = "Hello MGbot"

    if interactive:
        text = ask_str("Введите текст для вывода на дисплей (utf-8)", default_text)
    else:
        text = default_text

    print(f"Отправляю текст на дисплей: {text!r}")
    conveyor.display_text(text)
    print("Текст отправлен.")


def test_conveyor_buzzer(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: подача звукового сигнала (пьезо-излучатель) на конвейере.

    Согласно инструкции:
        set_buzz_tone(level) — level в диапазоне 1..15.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ ЗВУКОВОГО СИГНАЛА (BUZZER) ===")
    default_level = 5

    if interactive:
        level = ask_int("Введите уровень сигнала (1..15)", default_level)
    else:
        level = default_level

    level = _clamp(level, 1, 15)
    print(f"Подаю звуковой сигнал с уровнем {level}...")
    conveyor.set_buzz_tone(level)
    print("Команда отправлена (поведение и длительность зависят от прошивки контроллера).")


def _pretty_print_sensors(data: Dict[str, Any]) -> None:
    """
    Красивый вывод структуры данных с датчиков.
    Ожидаемые поля по инструкции:
        - DistanceSensor
        - ColorSensor (объект с полями R, G, B, Prox)
        - Prox (общая близость к ColorSensor)
    """
    print("Сырые данные датчиков:", data)

    distance = data.get("DistanceSensor")
    color = data.get("ColorSensor")
    prox = data.get("Prox")

    if distance is not None:
        print(f"  DistanceSensor: {distance}")

    if isinstance(color, dict):
        r = color.get("R")
        g = color.get("G")
        b = color.get("B")
        c_prox = color.get("Prox")
        print("  ColorSensor:")
        print(f"    R={r}, G={g}, B={b}, Prox={c_prox}")
    elif color is not None:
        print(f"  ColorSensor: {color}")

    if prox is not None:
        print(f"  Prox (top-level): {prox}")


def test_conveyor_sensors(manipulator: MEdu, interactive: bool = True) -> None:
    """
    Тест: чтение данных с датчиков конвейера.

    Используется:
        manipulator.mgbot_conveyer.get_sensors_data(True)
    По инструкции True — вернуть данные в виде JSON.
    """
    require_conveyor(manipulator)
    conveyor = manipulator.mgbot_conveyer

    print("\n=== ТЕСТ ДАТЧИКОВ КОНВЕЙЕРА ===")
    default_iterations = 5
    default_delay = 0.5

    if interactive:
        iterations = ask_int("Сколько раз опросить датчики?", default_iterations)
        delay = ask_float("Пауза между опросами (сек.)", default_delay)
    else:
        iterations = default_iterations
        delay = default_delay

    iterations = max(1, iterations)

    for i in range(iterations):
        print(f"\n--- Опрос #{i + 1} ---")
        raw_data: Optional[Any] = conveyor.get_sensors_data(True)
        print(f"Тип возвращаемых данных: {type(raw_data)}")

        parsed: Optional[Dict[str, Any]] = None

        if isinstance(raw_data, dict):
            parsed = raw_data
        elif isinstance(raw_data, str):
            try:
                parsed = json.loads(raw_data)
            except json.JSONDecodeError as e:
                print("Не удалось распарсить JSON из строки:", e)
        else:
            print("Неизвестный формат данных от get_sensors_data(True).")

        if parsed is not None:
            _pretty_print_sensors(parsed)
        else:
            print("Данные датчиков (как есть):", raw_data)

        if i < iterations - 1:
            time.sleep(delay)


# ================== ТОЧКА ВХОДА ==================

def main():
    manipulator: Optional[MEdu] = None

    try:
        manipulator = create_manipulator()

        # ==== ВЫБОР НУЖНОГО ТЕСТА ====
        # Раскомментируй одну или несколько строк ниже:

        # test_conveyor_speed(manipulator, interactive=True)
        # test_conveyor_servo_angle(manipulator, interactive=True)
        # test_conveyor_led_color(manipulator, interactive=True)
        # test_conveyor_display_text(manipulator, interactive=True)
        # test_conveyor_buzzer(manipulator, interactive=True)
        # test_conveyor_sensors(manipulator, interactive=True)

    except Exception as e:
        print(f"\nОШИБКА: {e}")
    finally:
        # Попытка аккуратно остановить конвейер и движение манипулятора
        if manipulator is not None:
            try:
                if hasattr(manipulator, "mgbot_conveyer"):
                    print("Останавливаю конвейер (скорость 0)...")
                    manipulator.mgbot_conveyer.set_speed_motors(0)
            except Exception as e:
                print(f"Ошибка при остановке конвейера: {e}")

            try:
                print("Останавливаю движение манипулятора (stop_movement)...")
                manipulator.stop_movement(timeout_seconds=5.0)
            except Exception as e:
                print(f"Ошибка при stop_movement: {e}")


if __name__ == "__main__":
    main()
