from sdk.manipulators.medu import MEdu
from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
    PlannerType
)

from sdk.utils.enums import  ServoControlType
import time
import threading
import json

# ============================================================================
# ГЛОБАЛЬНЫЕ НАСТРОЙКИ
# ============================================================================

# Параметры подключения к манипулятору

HOST = "10.5.0.2"   # IP манипулятора
CLIENT_ID = "test-client"         # ID клиента
LOGIN = "user"              # Логин
PASSWORD = "pass"           # Пароль


# GPIO пин для светодиода
GPIO_LED_PIN = "/dev/gpiochip4/e1_pin"
GPIO_BUTTON_PIN = "/dev/gpiochip4/e2_pin"


def parse_joint_state(json_str):
    """
    Парсит строку JSON, представляющую JointState из ROS,
    и возвращает словарь с данными по суставам.
    """
    data = json.loads(json_str)

    # Извлекаем списки
    names = data["name"]
    positions = data["position"]
    velocities = data["velocity"]
    efforts = data["effort"]

    # Собираем словарь: имя сустава -> его данные
    joint_dict = {}
    for i, name in enumerate(names):
        joint_dict[name] = {
            "position": positions[i],
            "velocity": velocities[i],
            "effort": efforts[i]
        }

    # Добавляем заголовок, если нужно
    joint_dict["_header"] = data["header"]

    return joint_dict


def parse_tool0(json_str):
    """
    Парсит JSON-строку с данными инструментов и возвращает только данные tool0.
    """
    data = json.loads(json_str)
    tool0 = data.get("tool0", {})

    # Проверка на наличие обязательных полей (опционально)
    if "position" not in tool0 or "orientation" not in tool0:
        raise ValueError("Некорректный формат данных: отсутствует position или orientation в tool0")

    return {
        "position": {
            "x": tool0["position"]["x"],
            "y": tool0["position"]["y"],
            "z": tool0["position"]["z"]
        },
        "orientation": {
            "x": tool0["orientation"]["x"],
            "y": tool0["orientation"]["y"],
            "z": tool0["orientation"]["z"],
            "w": tool0["orientation"]["w"]
        }
    }

def get_dist_move(manipulator):
    curr_pos = "None"
    while True:
        try:
            value = manipulator.mgbot_conveyer.get_sensors_data(True)
            parsed = json.loads(value)
            distance = parsed["DistanceSensor"]
            if distance >= 282:
                if curr_pos != "4":
                    manipulator.move_to_angles(
                        povorot_osnovaniya=0.0,  # угол поворота основания [рад]
                        privod_plecha=-0.35,  # угол плеча [рад]
                        privod_strely=-0.75,  # угол стрелы [рад]
                        v_osnovaniya=0.0,  # скорость основания [рад/с]
                        v_plecha=0.0,  # скорость плеча [рад/с]
                        v_strely=0.0,  # скорость стрелы [рад/с]
                        velocity_factor=0.3,  # коэффициент скорости
                        acceleration_factor=0.1,  # коэффициент ускорения
                    )
                    curr_pos = "4"
            elif distance > 215 and distance < 282:
                if curr_pos != "3":
                    manipulator.move_to_angles(
                        povorot_osnovaniya=-0.52,  # угол поворота основания [рад]
                        privod_plecha=-0.35,  # угол плеча [рад]
                        privod_strely=-0.75,  # угол стрелы [рад]
                        v_osnovaniya=0.0,  # скорость основания [рад/с]
                        v_plecha=0.0,  # скорость плеча [рад/с]
                        v_strely=0.0,  # скорость стрелы [рад/с]
                        velocity_factor=0.3,  # коэффициент скорости
                        acceleration_factor=0.1,  # коэффициент ускорения
                    )
                    curr_pos = "3"
                    manipulator.play_audio(file_name="warning.wav", timeout_seconds=5.0)
            elif distance < 215 and distance > 136:
                if curr_pos != "2":
                    manipulator.move_to_angles(
                        povorot_osnovaniya=-1.05,  # угол поворота основания [рад]
                        privod_plecha=-0.35,  # угол плеча [рад]
                        privod_strely=-0.75,  # угол стрелы [рад]
                        v_osnovaniya=0.0,  # скорость основания [рад/с]
                        v_plecha=0.0,  # скорость плеча [рад/с]
                        v_strely=0.0,  # скорость стрелы [рад/с]
                        velocity_factor=0.3,  # коэффициент скорости
                        acceleration_factor=0.1,  # коэффициент ускорения
                    )
                    curr_pos = "2"
                    manipulator.play_audio(file_name="warning.wav", timeout_seconds=5.0)
                    manipulator.play_audio(file_name="warning.wav", timeout_seconds=5.0)
                    manipulator.play_audio(file_name="warning.wav", timeout_seconds=5.0)
            elif distance < 136:
                if curr_pos != "1":
                    manipulator.move_to_angles(
                        povorot_osnovaniya=-1.57,  # угол поворота основания [рад]
                        privod_plecha=-0.35,  # угол плеча [рад]
                        privod_strely=-0.75,  # угол стрелы [рад]
                        v_osnovaniya=0.0,  # скорость основания [рад/с]
                        v_plecha=0.0,  # скорость плеча [рад/с]
                        v_strely=0.0,  # скорость стрелы [рад/с]
                        velocity_factor=0.3,  # коэффициент скорости
                        acceleration_factor=0.1,  # коэффициент ускорения
                    )
                    curr_pos = "1"
                manipulator.play_audio(file_name="warning.wav", timeout_seconds=5.0)
        except Exception as e:
            print(f"   ❌ Ошибка чтения: {e}")
            manipulator.nozzle_power(False)



def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  УНИВЕРСАЛЬНЫЙ СКРИПТ PROMOBOT M EDU                        ║
║  SDK версия: 0.6.8                                          ║
║  Выберите функцию в коде и раскомментируйте её              ║
╚══════════════════════════════════════════════════════════════╝

🆕 НОВОЕ В SDK 0.6.8:
  - move_to_angles() с параметрами скорости
  - play_audio() - воспроизведение звука
  - get_gpio_value() - чтение GPIO
  - subscribe_to_joint_state() - подписка на суставы
  - track_coordinates_polling() - альтернатива подписке на координаты
    """)

    print(f"🔌 Подключение к манипулятору {HOST}...")
    try:
        manipulator = MEdu(
            host=HOST,
            client_id=CLIENT_ID,
            login=LOGIN,
            password=PASSWORD
        )
        manipulator.connect()
        manipulator.get_control()
        print("✅ Подключение успешно!\n")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return

    # ========================================================================
    # ВЫБЕРИТЕ ФУНКЦИЮ (раскомментируйте нужную)
    # ========================================================================

    try:
        get_dist_move(manipulator)
        #manipulator.manage_gripper(rotation=0, gripper= 0)
        #manipulator.play_audio(file_name="warning.wav", timeout_seconds=10.0)
        # manipulator.move_to_angles(
        #     povorot_osnovaniya=-0.52,  # угол поворота основания [рад]
        #     privod_plecha=-0.35,  # угол плеча [рад]
        #     privod_strely=-0.75,  # угол стрелы [рад]
        #     v_osnovaniya=0.0,  # скорость основания [рад/с]
        #     v_plecha=0.0,  # скорость плеча [рад/с]
        #     v_strely=0.0,  # скорость стрелы [рад/с]
        #     velocity_factor=0.1,  # коэффициент скорости
        #     acceleration_factor=0.1,  # коэффициент ускорения
        # )

    except KeyboardInterrupt:
        print("\n\n⚠️  Программа прервана пользователем")
        manipulator.stop_movement(timeout_seconds=5.0)
    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}")
        manipulator.stop_movement(timeout_seconds=5.0)
    finally:
        print("\n👋 Программа завершена")


if __name__ == "__main__":
    main()
