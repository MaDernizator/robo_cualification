"""
Тестовый скрипт для проверки работы манипулятора MEdu через pm_python_sdk.

Файл устроен так, чтобы:
- были отдельные функции для тестирования разных возможностей;
- в конце файла можно было просто раскомментировать нужный вызов и запустить только его;
- внутри тестовых функций параметры (координаты, углы, номера каналов и т.п.) удобно вводились с клавиатуры
  с разумными значениями по умолчанию.

Перед использованием:
1. Установите pm_python_sdk (если ещё не установлен).
2. Убедитесь, что этот файл запускается в том же окружении, где доступен пакет `sdk`.
"""

from sdk.manipulators.medu import MEdu
from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
    PlannerType,
)
from sdk.errors import SdkError, CommandError, CommandTimeout, ConnectionError

from typing import Optional


# ----- Настройки по умолчанию для подключения -----

DEFAULT_HOST = "192.168.0.183"
DEFAULT_CLIENT_ID = "test-client"
DEFAULT_LOGIN = "user"
DEFAULT_PASSWORD = "pass"


# ----- Вспомогательные функции ввода -----

def ask_str(prompt: str, default: Optional[str] = None) -> str:
    if default:
        full = f"{prompt} [{default}]: "
    else:
        full = f"{prompt}: "
    s = input(full).strip()
    return s or (default or "")


def ask_float(prompt: str, default: float) -> float:
    while True:
        s = input(f"{prompt} [{default}]: ").strip()
        if not s:
            return default
        try:
            # поддержка запятой как разделителя
            s = s.replace(",", ".")
            return float(s)
        except ValueError:
            print("Введите число (можно с точкой или запятой).")


def ask_int(prompt: str, default: int) -> int:
    while True:
        s = input(f"{prompt} [{default}]: ").strip()
        if not s:
            return default
        try:
            return int(s)
        except ValueError:
            print("Введите целое число.")


def ask_bool(prompt: str, default: bool = True) -> bool:
    default_str = "y" if default else "n"
    s = input(f"{prompt} [y/n, по умолчанию {default_str}]: ").strip().lower()
    if not s:
        return default
    return s in ("y", "yes", "д", "да")


# ----- Функции инициализации/подключения -----

def init_manipulator() -> MEdu:
    """
    Создаёт объект MEdu, подключается к роботу и берёт управление.
    Все параметры можно изменить с клавиатуры.
    """
    print("=== Параметры подключения ===")
    host = ask_str("IP адрес манипулятора", DEFAULT_HOST)
    client_id = ask_str("client_id (произвольная строка)", DEFAULT_CLIENT_ID)
    login = ask_str("Логин", DEFAULT_LOGIN)
    password = ask_str("Пароль", DEFAULT_PASSWORD)

    manip = MEdu(host, client_id, login, password)
    manip.connect()
    print("Подключение к MQTT установлено.")

    manip.get_control()
    print("Управление манипулятором получено.")

    return manip


def test_connection_only() -> None:
    """
    Тест только подключения и получения управления.
    Удобно запускать, когда нужно просто проверить сеть/доступ.
    """
    manip: Optional[MEdu] = None
    try:
        manip = init_manipulator()
        print("Тест подключения успешно завершён.")
    except (ConnectionError, CommandTimeout, CommandError, SdkError) as e:
        print("Ошибка SDK при подключении:", e)
    except Exception as e:
        print("Непредвиденная ошибка:", e)
    finally:
        if manip is not None:
            try:
                manip.disconnect()
                print("Соединение с манипулятором закрыто.")
            except Exception:
                pass


# ----- Тесты получения состояния -----

def test_read_states(manip: MEdu) -> None:
    """
    Тест чтения различных состояний манипулятора.
    """
    print("=== Тест: чтение состояний манипулятора ===")

    try:
        coords = manip.get_cartesian_coordinates()
        print("Текущие декартовы координаты (как есть из SDK):")
        print(coords)
    except Exception as e:
        print("Не удалось получить декартовы координаты:", e)

    try:
        joints = manip.get_joint_state()
        print("Текущее состояние суставов (как есть из SDK):")
        print(joints)
    except Exception as e:
        print("Не удалось получить состояние суставов:", e)

    try:
        home = manip.get_home_position()
        print("Домашняя позиция (home_position):")
        print(home)
    except Exception as e:
        print("Не удалось получить домашнюю позицию:", e)

    try:
        print("Запрашиваем ограничения по суставам (joint limits)...")
        manip.get_joint_limits()
        print("Ограничения по суставам успешно запрошены (подробности см. лог манипулятора, если он их пишет).")
    except Exception as e:
        print("Не удалось получить ограничения по суставам:", e)


# ----- Тесты движения -----

def test_move_cartesian(manip: MEdu) -> None:
    """
    Тест движения в декартовых координатах (x, y, z + ориентация кватернионом).
    Все значения можно ввести с клавиатуры.
    """
    print("=== Тест: движение в декартовых координатах ===")

    print("Сначала читаем текущие координаты (для ориентира)...")
    try:
        current = manip.get_cartesian_coordinates()
        print("Текущие координаты:", current)
    except Exception as e:
        print("Не удалось прочитать текущие координаты:", e)

    print("\nУкажите целевую точку (в метрах) и ориентацию (кватернион).")
    x = ask_float("X, м", 0.3)
    y = ask_float("Y, м", 0.0)
    z = ask_float("Z, м", 0.2)

    print("Ориентация задаётся кватернионом (qx, qy, qz, qw).")
    qx = ask_float("qx", 0.0)
    qy = ask_float("qy", 0.0)
    qz = ask_float("qz", 0.0)
    qw = ask_float("qw", 1.0)

    vel = ask_float("Коэффициент скорости (0.0..1.0)", 0.2)
    acc = ask_float("Коэффициент ускорения (0.0..1.0)", 0.2)
    use_lin = ask_bool("Использовать линейный планировщик LIN? (иначе будет PTP)", True)
    planner = PlannerType.LIN if use_lin else PlannerType.PTP

    pos = MoveCoordinatesParamsPosition(x, y, z)
    ori = MoveCoordinatesParamsOrientation(qx, qy, qz, qw)

    print("\nОтправляем команду на движение...")
    manip.move_to_coordinates(
        pos,
        ori,
        velocity_scaling_factor=vel,
        acceleration_scaling_factor=acc,
        planner_type=planner,
    )
    print("Манипулятор доехал до заданных декартовых координат.")


def test_move_joints(manip: MEdu) -> None:
    """
    Тест движения в пространстве суставов (углы в радианах).
    """
    print("=== Тест: движение по суставным координатам ===")

    print("Сначала читаем текущее состояние суставов (для ориентира)...")
    try:
        joints = manip.get_joint_state()
        print("Текущее состояние суставов:", joints)
    except Exception as e:
        print("Не удалось прочитать состояние суставов:", e)

    print("\nУкажите целевые углы (в радианах).")
    base_angle = ask_float("Угол основания (povorot_osnovaniya), рад", 0.0)
    shoulder_angle = ask_float("Угол плеча (privod_plecha), рад", 0.0)
    elbow_angle = ask_float("Угол стрелы (privod_strely), рад", 1.0)

    print("Можно дополнительно задать скорости по суставам (рад/с).")
    v_base = ask_float("Скорость основания, рад/с", 0.0)
    v_shoulder = ask_float("Скорость плеча, рад/с", 0.0)
    v_elbow = ask_float("Скорость стрелы, рад/с", 0.0)

    vel_factor = ask_float("Коэффициент скорости (0.0..1.0)", 0.1)
    acc_factor = ask_float("Коэффициент ускорения (0.0..1.0)", 0.1)

    print("\nОтправляем команду на движение...")
    manip.move_to_angles(
        base_angle,
        shoulder_angle,
        elbow_angle,
        v_base,
        v_shoulder,
        v_elbow,
        velocity_factor=vel_factor,
        acceleration_factor=acc_factor,
    )
    print("Манипулятор доехал до заданных суставных координат.")


# ----- Тесты насадок и выходов -----

def test_nozzle_power(manip: MEdu) -> None:
    """
    Тест включения/выключения питания на разъёмах стрелы.
    """
    print("=== Тест: питание на стрелу (nozzle_power) ===")
    power_on = ask_bool("Включить питание на разъёмы стрелы?", True)
    manip.nozzle_power(power_on)
    print("Команда отправлена. Текущее состояние питания должно измениться.")


def test_gripper(manip: MEdu) -> None:
    """
    Тест управления гриппером.
    Перед управлением гриппером нужно включить питание на стреле.
    """
    print("=== Тест: гриппер (manage_gripper) ===")

    ensure_power = ask_bool("Включить питание на стреле (nozzle_power)?", True)
    if ensure_power:
        manip.nozzle_power(True)
        print("Питание на стреле включено.")

    print("\nНастройка движения гриппера.")
    change_rotation = ask_bool("Изменить поворот насадки (rotation)?", True)
    rotation: Optional[int] = None
    if change_rotation:
        rotation = ask_int("Поворот насадки, градусы", 10)

    change_grip = ask_bool("Изменить сжатие гриппера (gripper)?", True)
    gripper: Optional[int] = None
    if change_grip:
        gripper = ask_int("Сжатие гриппера, градусы", 10)

    if rotation is None and gripper is None:
        print("Нечего изменять (rotation и gripper = None). Тест прерван.")
        return

    print("\nОтправляем команду на управление гриппером...")
    manip.manage_gripper(rotation=rotation, gripper=gripper)
    print("Команда на управление гриппером выполнена.")



def test_play_audio(manip: MEdu) -> None:
    """
    Тест проигрывания аудио-файла с манипулятора.
    Имя файла задаётся так, как его ожидает контроллер (смотрите документацию и список файлов на манипуляторе).
    """
    print("=== Тест: проигрывание аудио (play_audio) ===")
    file_name = ask_str("Имя аудио-файла (например, '0.wav')", "0.wav")
    manip.play_audio(file_name)
    print("Команда на воспроизведение аудио отправлена.")


# ----- Точка входа -----

if __name__ == "__main__":
    # Вариант 1: проверить только подключение (без остальных тестов)
    # test_connection_only()

    # Вариант 2: подключиться один раз и запускать нужные тесты по очереди
    manipulator: Optional[MEdu] = None
    try:
        manipulator = init_manipulator()

        # Раскомментируйте те строки, которые хотите проверить сейчас:

        # test_read_states(manipulator)
        test_move_cartesian(manipulator)
        # test_move_joints(manipulator)
        # test_gripper(manipulator)
        # test_play_audio(manipulator)

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
