"""
conveyor_control.py — удобные обёртки для работы с конвейером MGbot

Файл предназначен для использования в "боевой" логике:
вы просто вызываете функции вроде
    run_conveyor_speed(30, duration_sec=5)
а вся необходимая подготовка (подключение к манипулятору, проверка конвейера)
делается внутри.

Требования:
    - Установлен SDK, работает импорт:
          from sdk.manipulators.medu import MEdu
    - Заполнены параметры подключения HOST / CLIENT_ID / LOGIN / PASSWORD
"""

import json
import time
from typing import Any, Dict, List, Optional

from sdk.manipulators.medu import MEdu


# ================== НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ==================

# !!! ЗАМЕНИ эти значения на реальные для своего манипулятора !!!
HOST = "192.168.0.183"   # IP манипулятора
CLIENT_ID = "test-client"         # ID клиента
LOGIN = "user"              # Логин
PASSWORD = "pass"           # Пароль


# ================== БАЗОВЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def _clamp_int(value: int, min_val: int, max_val: int) -> int:
    """Обрезает значение до диапазона [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def _create_manipulator() -> MEdu:
    """
    Создаёт объект манипулятора, подключается и захватывает управление.

    Выбрасывает исключения, если подключиться не удалось.
    """
    print(f"[INFO] Подключение к манипулятору {HOST!r} (client_id={CLIENT_ID})...")
    manip = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    manip.connect()
    manip.get_control()
    print("[INFO] Управление манипулятором захвачено.")

    if not hasattr(manip, "mgbot_conveyer"):
        raise RuntimeError(
            "У объекта манипулятора нет атрибута 'mgbot_conveyer'. "
            "Проверь, что конвейер подключён и SDK поддерживает работу с ним."
        )

    return manip


def _safe_cleanup(manipulator: Optional[MEdu]) -> None:
    """
    Пытается корректно остановить конвейер и движение манипулятора.

    Вызывается в блоке finally всех публичных функций.
    """
    if manipulator is None:
        return

    try:
        if hasattr(manipulator, "mgbot_conveyer"):
            print("[CLEANUP] Останавливаю конвейер (скорость 0)...")
            manipulator.mgbot_conveyer.set_speed_motors(0)
    except Exception as e:
        print(f"[CLEANUP] Ошибка при остановке конвейера: {e}")

    try:
        print("[CLEANUP] Останавливаю движение манипулятора (stop_movement)...")
        manipulator.stop_movement(timeout_seconds=5.0)
    except Exception as e:
        print(f"[CLEANUP] Ошибка при stop_movement: {e}")


# ================== ВЫСОКОУРОВНЕВЫЕ ОБЁРТКИ ДЛЯ ЛОГИКИ ==================
# Каждую из этих функций удобно вызывать из вашей логики напрямую.
# Внутри они сами:
#   * создают и настраивают manipulator (MEdu)
#   * получают доступ к manipulator.mgbot_conveyer
#   * выполняют нужное действие
#   * выполняют безопасную остановку в finally


def run_conveyor_speed(speed_percent: int,
                       duration_sec: Optional[float] = None) -> None:
    """
    Запустить конвейер с заданной скоростью, опционально на фиксированное время.

    Параметры:
        speed_percent: int
            Скорость движения ленты в процентах от максимальной.
            Диапазон значений: 0..100
                0   — конвейер стоит,
                1-30 — медленное движение (обычно безопасно для экспериментов),
                30-70 — средняя скорость,
                70-100 — высокая скорость (использовать с осторожностью).

        duration_sec: float | None
            На какое время запустить конвейер (в секундах).
            - Если None — просто установит скорость и вернётся,
              дальше вы сами отвечаете за остановку.
            - Если задано число (например, 3.0) — конвейер будет
              работать примерно это время, после чего автоматически
              остановится (скорость будет сброшена в 0).

    Примеры использования:
        # Запустить конвейер на 5 секунд, ~30% мощности:
        run_conveyor_speed(30, duration_sec=5)

        # Просто установить скорость 50% и не трогать дальше:
        run_conveyor_speed(50)
    """
    manip: Optional[MEdu] = None
    try:
        manip = _create_manipulator()
        conveyor = manip.mgbot_conveyer

        speed = _clamp_int(speed_percent, 0, 100)
        print(f"[ACTION] Устанавливаю скорость конвейера: {speed}%")
        conveyor.set_speed_motors(speed)

        if duration_sec is not None and speed > 0:
            print(f"[INFO] Конвейер будет работать ~{duration_sec} секунд...")
            time.sleep(duration_sec)
            print("[ACTION] Останавливаю конвейер (скорость 0) после таймера.")
            conveyor.set_speed_motors(0)

    except Exception as e:
        print(f"[ERROR] run_conveyor_speed: {e}")
        raise
    finally:
        _safe_cleanup(manip)


def set_conveyor_led_color(r: int, g: int, b: int) -> None:
    """
    Установить цвет RGB-светодиода на конвейере.

    Параметры:
        r, g, b: int
            Компоненты цвета красная/зелёная/синяя в диапазоне 0..255.
            0   — компонента выключена
            255 — максимальная яркость компоненты

            Примеры:
                (255, 0, 0)   — чисто красный
                (0, 255, 0)   — чисто зелёный
                (0, 0, 255)   — чисто синий
                (255, 255, 0) — жёлтый
                (255, 255, 255) — белый (если поддерживается, может быть очень ярким)

    Примеры использования:
        set_conveyor_led_color(255, 0, 0)     # красный
        set_conveyor_led_color(0, 255, 0)     # зелёный
        set_conveyor_led_color(0, 0, 255)     # синий
    """
    manip: Optional[MEdu] = None
    try:
        manip = _create_manipulator()
        conveyor = manip.mgbot_conveyer

        r = _clamp_int(r, 0, 255)
        g = _clamp_int(g, 0, 255)
        b = _clamp_int(b, 0, 255)

        print(f"[ACTION] Устанавливаю цвет LED конвейера: R={r}, G={g}, B={b}")
        conveyor.set_led_color(r, g, b)
        print("[INFO] Цвет LED установлен.")

    except Exception as e:
        print(f"[ERROR] set_conveyor_led_color: {e}")
        raise
    finally:
        _safe_cleanup(manip)


def display_text_on_conveyor(text: str) -> None:
    """
    Вывести строку текста на дисплей конвейера.

    Параметры:
        text: str
            Строка (обычно UTF-8), которая будет отображена.
            Длина и набор поддерживаемых символов зависят от прошивки
            и самого дисплея. Практически:
                - латиница и цифры работают стабильно,
                - кириллица зависит от устройства (может отображаться неверно).

    Примеры использования:
        display_text_on_conveyor("Hello MGbot")
        display_text_on_conveyor("Box #12")
    """
    manip: Optional[MEdu] = None
    try:
        manip = _create_manipulator()
        conveyor = manip.mgbot_conveyer

        print(f"[ACTION] Отправляю текст на дисплей конвейера: {text!r}")
        conveyor.display_text(text)
        print("[INFO] Текст отправлен.")

    except Exception as e:
        print(f"[ERROR] display_text_on_conveyor: {e}")
        raise
    finally:
        _safe_cleanup(manip)


def read_conveyor_sensors(iterations: int = 1,
                          delay_sec: float = 0.0,
                          verbose: bool = True) -> List[Dict[str, Any]]:
    """
    Считать данные с датчиков конвейера 1 или несколько раз.

    Под капотом вызывается:
        manipulator.mgbot_conveyer.get_sensors_data(True)

    Ожидаемый формат данных (по инструкции SDK):
        {
            "DistanceSensor": <число или структура>,
            "ColorSensor": {
                "R": <int>,
                "G": <int>,
                "B": <int>,
                "Prox": <int или float>   # близость/освещённость
            },
            "Prox": <int или float>       # общая близость по верхнему уровню
        }

    Параметры:
        iterations: int
            Сколько раз подряд опросить датчики.
            - 1  — один раз (типичный случай),
            - >1 — использовать для наблюдения в динамике.

        delay_sec: float
            Пауза между опросами, в секундах.
            - 0.0   — без паузы (быстрый опрос),
            - 0.1-1 — комфортная периодичность для логирования.

        verbose: bool
            Если True — печатает данные в консоль в удобочитаемом виде.
            Если False — работает тихо, просто возвращает список
                         считанных словарей.

    Возвращает:
        List[Dict[str, Any]] — список словарей с разобранными данными датчиков.
        Длина списка = iterations (если не было ошибок парсинга).

    Примеры использования:
        # Один опрос датчиков:
        data_list = read_conveyor_sensors()
        last_data = data_list[-1]

        # Пять опросов с интервалом 0.5 сек:
        history = read_conveyor_sensors(iterations=5, delay_sec=0.5)
    """
    manip: Optional[MEdu] = None
    results: List[Dict[str, Any]] = []

    def _pretty_print(data: Dict[str, Any]) -> None:
        """Локальная функция для красивого вывода данных датчиков."""
        print("  Сырые данные:", data)

        distance = data.get("DistanceSensor")
        color = data.get("ColorSensor")
        prox = data.get("Prox")

        if distance is not None:
            print(f"    DistanceSensor: {distance}")

        if isinstance(color, dict):
            r = color.get("R")
            g = color.get("G")
            b = color.get("B")
            c_prox = color.get("Prox")
            print("    ColorSensor:")
            print(f"      R={r}, G={g}, B={b}, Prox={c_prox}")
        elif color is not None:
            print(f"    ColorSensor: {color}")

        if prox is not None:
            print(f"    Prox (top-level): {prox}")

    try:
        manip = _create_manipulator()
        conveyor = manip.mgbot_conveyer

        iterations = max(1, int(iterations))
        delay_sec = float(delay_sec)

        for i in range(iterations):
            if verbose:
                print(f"[ACTION] Опрос датчиков #{i + 1}/{iterations}...")

            raw_data = conveyor.get_sensors_data(True)
            parsed: Optional[Dict[str, Any]] = None

            if isinstance(raw_data, dict):
                parsed = raw_data
            elif isinstance(raw_data, str):
                try:
                    parsed = json.loads(raw_data)
                except json.JSONDecodeError as e:
                    print(f"[WARN] Не удалось распарсить JSON из строки: {e}")
            else:
                print("[WARN] Неизвестный тип данных от get_sensors_data(True):", type(raw_data))

            if parsed is not None:
                results.append(parsed)
                if verbose:
                    _pretty_print(parsed)
            else:
                if verbose:
                    print("[WARN] Данные датчиков не распознаны, сохраняю как пустой словарь.")
                results.append({})

            if i < iterations - 1 and delay_sec > 0:
                time.sleep(delay_sec)

        return results

    except Exception as e:
        print(f"[ERROR] read_conveyor_sensors: {e}")
        raise
    finally:
        _safe_cleanup(manip)


# ================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ==================
# Этот блок не обязателен; можно удалить или оставить как справку.
if __name__ == "__main__":
    # Примеры "ручного" использования:
    # 1. Прогнать конвейер на 3 секунды с 40% мощности:
    run_conveyor_speed(10, duration_sec=5)

    # 2. Поменять цвет LED на зелёный:
    # set_conveyor_led_color(0, 255, 0)

    # 3. Вывести текст:
    # display_text_on_conveyor("Test 123")

    # 4. Опросить датчики 5 раз с интервалом 0.5 секунды:
    # data = read_conveyor_sensors(iterations=5, delay_sec=0.5, verbose=True)
    # print("Последние данные:", data[-1] if data else None)

    pass
