"""
medu_wrappers.py

Утилитные функции-обёртки для удобной работы с манипулятором MEdu.

Идея: в основном коде вы пишете бизнес-логику и вызываете уже готовые функции
из этого файла, не вспоминая детали SDK.

Обычный паттерн использования:

    from medu_wrappers import (
        connect_medu,
        read_states,
        move_cartesian,
        move_joints,
        set_gripper,
        play_audio,
    )

    manip = connect_medu()  # один раз на программу

    move_cartesian(manip, x=0.3, y=0.0, z=0.2)
    set_gripper(manip, rotation_deg=30, gripper_deg=40)
    play_audio(manip, "start.wav")

"""

from typing import Any, Dict, Optional

from sdk.manipulators.medu import MEdu
from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
    PlannerType,
)
from sdk.errors import SdkError, CommandError, CommandTimeout, ConnectionError


# -----------------------------------------------------------------------------
#  БАЗОВОЕ ПОДКЛЮЧЕНИЕ
# -----------------------------------------------------------------------------

# Значения по умолчанию — просто пример, поменяйте под свой стенд.

DEFAULT_HOST = "10.5.0.2"
DEFAULT_CLIENT_ID = "test-client"
DEFAULT_LOGIN = "user"
DEFAULT_PASSWORD = "pass"


def connect_medu(
    host: str = DEFAULT_HOST,
    client_id: str = DEFAULT_CLIENT_ID,
    login: str = DEFAULT_LOGIN,
    password: str = DEFAULT_PASSWORD,
) -> MEdu:
    """
    Подключение к манипулятору MEdu и захват управления.

    Параметры:
        host: str
            IP-адрес манипулятора. Его можно увидеть в MControl или
            настроить на самом манипуляторе.
        client_id: str
            Произвольная строка-идентификатор клиента (для MQTT).
            Можно вписать, например, название вашего проекта.
        login: str
            Логин для подключения к манипулятору (как в MControl).
        password: str
            Пароль для подключения к манипулятору (как в MControl).

    Возвращает:
        MEdu — готовый к работе объект манипулятора.

    Исключения:
        ConnectionError, CommandTimeout, CommandError, SdkError
        — при проблемах с сетью или ответом манипулятора.
    """
    manip = MEdu(host, client_id, login, password)
    manip.connect()       # Подключаемся к MQTT-серверу на манипуляторе
    manip.get_control()   # Захватываем управление (аналог "получить управление" в MControl)
    return manip


# -----------------------------------------------------------------------------
# 1. ЧТЕНИЕ СОСТОЯНИЙ
# -----------------------------------------------------------------------------

def read_states(manip: MEdu) -> Dict[str, Any]:
    """
    Получить набор основных состояний манипулятора в удобном виде.

    НЕ требует эксклюзивного управления, но предполагает, что соединение уже есть.

    Параметры:
        manip: MEdu
            Объект манипулятора, полученный через connect_medu().

    Возвращает словарь:
        {
            "cartesian":  ...  # текущие декартовы координаты TCP (x, y, z и ориентация)
            "joints":     ...  # состояние суставов (углы, скорости и т.д.)
            "home":       ...  # домашняя позиция манипулятора
        }

    Формат конкретных полей зависит от реализации SDK и версии прошивки.
    """
    states: Dict[str, Any] = {}

    # Текущие декартовы координаты инструмента (TCP)
    try:
        states["cartesian"] = manip.get_cartesian_coordinates()
    except Exception as e:
        states["cartesian_error"] = str(e)

    # Текущее состояние по суставам (углы и т.п.)
    try:
        states["joints"] = manip.get_joint_state()
    except Exception as e:
        states["joints_error"] = str(e)

    # Домашняя позиция (как настроена на манипуляторе)
    try:
        states["home"] = manip.get_home_position()
    except Exception as e:
        states["home_error"] = str(e)

    return states


# -----------------------------------------------------------------------------
# 2. ДВИЖЕНИЕ В ДЕКАРТОВЫХ КООРДИНАТАХ
# -----------------------------------------------------------------------------

def move_cartesian(
    manip: MEdu,
    x: float,
    y: float,
    z: float,
    qx: float = 0.0,
    qy: float = 0.0,
    qz: float = 0.0,
    qw: float = 1.0,
    velocity_scaling_factor: float = 0.1,
    acceleration_scaling_factor: float = 0.1,
    planner_type: PlannerType | str = "LIN",
    timeout_seconds: float = 30.0,
    throw_error: bool = True,
) -> None:
    """
    Движение в декартовых координатах (x, y, z + ориентация кватернионом).

    Внутри:
      - вызывает manip.get_control() (на случай, если управление было потеряно);
      - сам создаёт нужные объекты MoveCoordinatesParamsPosition/Orientation;
      - переводит строку 'LIN'/'PTP' в соответствующий PlannerType.

    ОБЯЗАТЕЛЬНО перед вызовом убедитесь, что координаты достижимы
    и не выводят манипулятор за пределы рабочего пространства.

    Параметры:
        manip: MEdu
            Объект манипулятора.

        x, y, z: float
            Целевая точка TCP в метрах в базовой системе координат.
            Примеры:
                x=0.3, y=0.0, z=0.2  — точка перед роботом чуть выше стола.
            Точный диапазон зависит от конкретного стенда; см. get_joint_limits()
            и документацию по рабочей зоне.

        qx, qy, qz, qw: float
            Ориентация TCP в виде кватерниона.
            По умолчанию (0, 0, 0, 1) — «без поворота» относительно базовой ориентации.

        velocity_scaling_factor: float
            Коэффициент скорости (0.0–1.0).
            0.1 = 10% от максимальной скорости,
            1.0 = полная скорость (использовать аккуратно при первых тестах).

        acceleration_scaling_factor: float
            Коэффициент ускорения (0.0–1.0).
            Аналогично velocity_scaling_factor, но для ускорения.

        planner_type: PlannerType | str
            Тип планировщика траектории:
                - "LIN" или PlannerType.LIN — линейное движение в пространстве TCP;
                - "PTP" или PlannerType.PTP — покомпонентное движение по суставам.
            По умолчанию используется линейный планировщик ("LIN").

        timeout_seconds: float
            Таймаут ожидания завершения движения в секундах.
            Если за это время движение не завершилось, будет ошибка/исключение.

        throw_error: bool
            Если True (по умолчанию), SDK выбросит исключение при ошибке.
            Если False, функция попытается вернуть ошибку в ответе, без исключения.

    Исключения:
        CommandTimeout, CommandError, ConnectionError, SdkError и др.
    """

    # На всякий случай повторно захватываем управление (операция идемпотентна).
    manip.get_control()

    # Подготовка позиции и ориентации в формате SDK.
    position = MoveCoordinatesParamsPosition(x, y, z)
    orientation = MoveCoordinatesParamsOrientation(qx, qy, qz, qw)

    # Нормализация типа планировщика: строка -> PlannerType
    if isinstance(planner_type, str):
        upper = planner_type.upper()
        if upper == "LIN":
            planner_enum = PlannerType.LIN
        elif upper == "PTP":
            planner_enum = PlannerType.PTP
        else:
            raise ValueError("planner_type должен быть 'LIN', 'PTP' или PlannerType.*")
    else:
        planner_enum = planner_type

    manip.move_to_coordinates(
        position,
        orientation,
        velocity_scaling_factor=velocity_scaling_factor,
        acceleration_scaling_factor=acceleration_scaling_factor,
        planner_type=planner_enum,
        timeout_seconds=timeout_seconds,
        throw_error=throw_error,
    )


# -----------------------------------------------------------------------------
# 3. ДВИЖЕНИЕ В ПРОСТРАНСТВЕ СУСТАВОВ (УГЛЫ)
# -----------------------------------------------------------------------------

def move_joints(
    manip: MEdu,
    povorot_osnovaniya: float,
    privod_plecha: float,
    privod_strely: float,
    v_osnovaniya: float = 0.0,
    v_plecha: float = 0.0,
    v_strely: float = 0.0,
    velocity_factor: float = 0.1,
    acceleration_factor: float = 0.1,
    timeout_seconds: float = 60.0,
    throw_error: bool = True,
) -> None:
    """
    Движение в пространстве суставов (move_to_angles).

    Параметры:
        manip: MEdu
            Объект манипулятора.

        povorot_osnovaniya: float
            Угол поворота основания в радианах.
            Положительное значение — поворот в одну сторону,
            отрицательное — в другую. Точный диапазон см. get_joint_limits().

        privod_plecha: float
            Угол плеча в радианах.

        privod_strely: float
            Угол стрелы (локтя) в радианах.

        v_osnovaniya, v_plecha, v_strely: float
            Заданные скорости (рад/с) для соответствующих суставов.
            Если не знаете, оставьте 0.0 — тогда будут использоваться
            стандартные значения из контроллера.

        velocity_factor: float
            Коэффициент скорости (0.0–1.0) для всего движения.
            0.1 — безопасное медленное движение.

        acceleration_factor: float
            Коэффициент ускорения (0.0–1.0) для всего движения.

        timeout_seconds: float
            Таймаут ожидания окончания движения.

        throw_error: bool
            Управление тем, будет ли SDK выбрасывать исключение при ошибке.

    Внутри:
        - вызывает manip.get_control();
        - напрямую использует метод move_to_angles().
    """

    manip.get_control()

    manip.move_to_angles(
        povorot_osnovaniya=povorot_osnovaniya,
        privod_plecha=privod_plecha,
        privod_strely=privod_strely,
        v_osnovaniya=v_osnovaniya,
        v_plecha=v_plecha,
        v_strely=v_strely,
        velocity_factor=velocity_factor,
        acceleration_factor=acceleration_factor,
        timeout_seconds=timeout_seconds,
        throw_error=throw_error,
    )


# -----------------------------------------------------------------------------
# 4. УПРАВЛЕНИЕ ГРИППЕРОМ
# -----------------------------------------------------------------------------

def set_gripper(
    manip: MEdu,
    rotation_deg: Optional[int] = None,
    gripper_deg: Optional[int] = None,
    ensure_nozzle_power: bool = True,
    timeout_seconds: float = 60.0,
    throw_error: bool = True,
) -> None:
    """
    Управление гриппером через метод manage_gripper().

    ВАЖНО:
        Для работы гриппера на стрелу должно быть подано питание:
        manip.nozzle_power(True).

    Эта обёртка по умолчанию сама включает питание (ensure_nozzle_power=True).

    Параметры:
        manip: MEdu
            Объект манипулятора.

        rotation_deg: Optional[int]
            Угол поворота насадки гриппера в градусах.
            Если None — поворот не изменяется.
            Типичные значения: около -90..+90, точный диапазон
            зависит от конкретной механики.

        gripper_deg: Optional[int]
            Положение (сжатие) губок гриппера в градусах.
            Чем больше значение — тем сильнее закрыт захват (зависит от калибровки).
            Если None — положение не изменяется.

        ensure_nozzle_power: bool
            Если True (по умолчанию), перед командой к грипперу будет вызвано
            manip.nozzle_power(True), чтобы гарантировать наличие питания на разъёмах стрелы.

        timeout_seconds: float
            Таймаут ожидания выполнения команды.

        throw_error: bool
            Выбрасывать ли исключения при ошибке.

    Примеры:
        # Просто слегка закрыть гриппер:
        set_gripper(manip, gripper_deg=30)

        # Повернуть гриппер вправо и сильно зажать:
        set_gripper(manip, rotation_deg=40, gripper_deg=70)
    """

    manip.get_control()

    if ensure_nozzle_power:
        # Включаем питание на разъёмах стрелы (нужно для гриппера, вакуума и т.п.)
        manip.nozzle_power(True)

    if rotation_deg is None and gripper_deg is None:
        # Нечего делать — но молча выходить тоже может запутать,
        # поэтому лучше бросить понятное исключение.
        raise ValueError(
            "set_gripper: хотя бы один из параметров rotation_deg или gripper_deg "
            "должен быть задан (не None)."
        )

    manip.manage_gripper(
        rotation=rotation_deg,
        gripper=gripper_deg,
        timeout_seconds=timeout_seconds,
        throw_error=throw_error,
    )


# -----------------------------------------------------------------------------
# 5. ВОСПРОИЗВЕДЕНИЕ АУДИО
# -----------------------------------------------------------------------------

def play_audio(
    manip: MEdu,
    file_name: str,
    timeout_seconds: float = 60.0,
    throw_error: bool = True,
) -> None:
    """
    Воспроизведение аудио-файла на манипуляторе.

    Параметры:
        manip: MEdu
            Объект манипулятора.

        file_name: str
            Имя аудио-файла на манипуляторе.
            Примеры:
                "0.wav"
                "start.wav"
            Файлы должны быть заранее загружены на устройство.

        timeout_seconds: float
            Таймаут ожидания выполнения команды. Как правило, можно оставлять
            значение по умолчанию.

        throw_error: bool
            Если True — при проблемах с воспроизведением будет выброшено исключение.

    Примеры:
        play_audio(manip, "0.wav")
        play_audio(manip, "start.wav", timeout_seconds=10.0)
    """

    manip.get_control()

    manip.play_audio(
        file_name,
        timeout_seconds=timeout_seconds,
        throw_error=throw_error,
    )


# -----------------------------------------------------------------------------
# 6. НЕБОЛЬШОЙ ПРИМЕР ИСПОЛЬЗОВАНИЯ В ЭТОМ ЖЕ ФАЙЛЕ (можно удалить)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Простейший пример: подключиться, прочитать состояния, съездить в точку
    и пощёлкать гриппером.

    Этот блок нужен только для быстрых ручных тестов.
    В своём проекте вы будете импортировать функции из этого файла.
    """
    manipulator: Optional[MEdu] = None

    try:
        manipulator = connect_medu()

        # 1) Чтение состояний
        # states = read_states(manipulator)
        # print("Состояния манипулятора:", states)

        # 2) Движение в декартовых координатах
        # move_cartesian(
        #     manipulator,
        #     x=0.30,
        #     y=0.00,
        #     z=0.20,
        #     velocity_scaling_factor=0.1,
        #     acceleration_scaling_factor=0.1,
        #     planner_type="LIN",
        # )

        # # 3) Движение по суставам
        # move_joints(
        #     manipulator,
        #     povorot_osnovaniya=0.0,
        #     privod_plecha=-0.3,
        #     privod_strely=-0.7,
        #     velocity_factor=0.1,
        #     acceleration_factor=0.1,
        # )

        # 4) Управление гриппером
        set_gripper(manipulator, rotation_deg=90, gripper_deg=-20)

        # 5) Воспроизведение аудио
        # play_audio(manipulator, "0.wav")

    except (ConnectionError, CommandTimeout, CommandError, SdkError) as e:
        print("Ошибка SDK:", e)
    except Exception as e:
        print("Непредвиденная ошибка:", e)
    finally:
        if manipulator is not None:
            try:
                manipulator.disconnect()
                print("Соединение с манипулятором закрыто.")
            except Exception:
                pass
