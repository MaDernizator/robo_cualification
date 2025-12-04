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

def gpio_read_test(manipulator):
    angle = 1
    moving = False
    timer = 0
    blink = False
    manipulator.set_servo_twist_mode()
    manipulator.nozzle_power(True)
    timer = time.time()
    while True:
        try:
            value = manipulator.get_gpio_value(
                name=GPIO_BUTTON_PIN,
                timeout_seconds=5.0,
                throw_error=True
            )
            print(f"   📍 Текущее значение: {value}")

            if value < 0.5:
                moving = True
            else:
                moving = False

            if moving:
                vals = parse_tool0(manipulator.get_cartesian_coordinates())

                data = vals
                print(data)
                curpos = data["position"]["y"]
                if curpos < -0.1:
                    angle = 1
                elif curpos > 0.1:
                    angle = -1

                linear_vel = {"x": 0 , "y": 0.1 * angle, "z": 0}
                angular_vel = {"rx": 0, "ry": 0, "rz": 0}
                manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
                tm = time.time() - timer
                print(tm)
                if tm > 1:
                    blink = not blink
                    manipulator.write_gpio(
                        name=GPIO_LED_PIN,
                        value=1 if blink else 0,
                        timeout_seconds=1,
                        throw_error=False
                    )
                    manipulator.manage_gripper(rotation=0, gripper=0 if blink else -30, timeout_seconds=1)
                    timer = time.time()
            time.sleep(0.1)
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

        gpio_read_test(manipulator)
        # vals = manipulator.get_cartesian_coordinates()
        # print(vals)
        # print(type(vals))
        # data = parse_joint_state(vals)
        # print(data)
        # print(data["povorot_osnovaniya"]["position"])
        # time.sleep(2)
        # while True:
        #     manipulator.get_gpio_value(name=GPIO_BUTTON_PIN)

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
