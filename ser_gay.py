"""
Универсальный скрипт для работы с Promobot M Edu
SDK версия: 0.6.8
Выберите нужную функцию в main() и раскомментируйте её

Обновления в 0.6.8:
- move_to_angles() с расширенными параметрами скорости
- Новый метод play_audio() для воспроизведения звука
- Новый метод get_gpio_value() для чтения GPIO
- Альтернативные методы для отслеживания координат

Автор: SDK Testing Suite
Версия: 2.0 (для SDK 0.6.8)
"""

from sdk.manipulators.medu import MEdu
from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
    PlannerType
)

from sdk.utils.enums import  ServoControlType
import time
import threading

# ============================================================================
# ГЛОБАЛЬНЫЕ НАСТРОЙКИ
# ============================================================================

# Параметры подключения к манипулятору

HOST = "192.168.0.183"   # IP манипулятора
CLIENT_ID = "test-client"         # ID клиента
LOGIN = "user"              # Логин
PASSWORD = "pass"           # Пароль


# GPIO пин для светодиода
GPIO_LED_PIN = "/dev/gpiochip4/e1_pin"


# ============================================================================
# ФУНКЦИИ ДЛЯ ВЫПОЛНЕНИЯ
# ============================================================================

def move_by_angles(manipulator):
    """
    Перемещение по углам суставов (обновлено для SDK 0.6.8)
    Теперь с расширенными параметрами скорости
    """
    print("\n" + "=" * 60)
    print("🎯 ПЕРЕМЕЩЕНИЕ ПО УГЛАМ СУСТАВОВ (SDK 0.6.8)")
    print("=" * 60)

    # Движение 1: Нулевая позиция (новый формат)
    print("\n1. Движение в нулевую позицию с параметрами скорости")
    manipulator.move_to_angles(
        povorot_osnovaniya=0.0,  # Основание [рад]
        privod_plecha=0.0,  # Плечо [рад]
        privod_strely=0.0,  # Стрела [рад]
        v_osnovaniya=0.0,  # Скорость основания [рад/с]
        v_plecha=0.0,  # Скорость плеча [рад/с]
        v_strely=0.0,  # Скорость стрелы [рад/с]
        velocity_factor=0.1,  # Коэффициент скорости
        acceleration_factor=0.1  # Коэффициент ускорения
    )
    time.sleep(3)
    print("   ✅ Нулевая позиция достигнута")

    # Движение 2: С повышенной скоростью
    print("\n2. Движение с повышенной скоростью (velocity_factor=0.3)")
    manipulator.move_to_angles(
        povorot_osnovaniya=0.785,  # 45 градусов
        privod_plecha=-0.524,  # -30 градусов
        privod_strely=-0.785,  # -45 градусов
        v_osnovaniya=0.0,
        v_plecha=0.0,
        v_strely=0.0,
        velocity_factor=0.3,  # Быстрее
        acceleration_factor=0.3
    )
    time.sleep(3)
    print("   ✅ Быстрое движение завершено")

    # Движение 3: С медленной скоростью
    print("\n3. Медленное точное движение (velocity_factor=0.05)")
    manipulator.move_to_angles(
        povorot_osnovaniya=-0.5,
        privod_plecha=-0.35,
        privod_strely=-0.75,
        v_osnovaniya=0.0,
        v_plecha=0.0,
        v_strely=0.0,
        velocity_factor=0.05,  # Медленно
        acceleration_factor=0.05
    )
    time.sleep(4)
    print("   ✅ Медленное движение завершено")

    # Движение 4: С заданными скоростями суставов
    print("\n4. Движение с явными скоростями суставов")
    manipulator.move_to_angles(
        povorot_osnovaniya=0.0,
        privod_plecha=0.0,
        privod_strely=0.0,
        v_osnovaniya=0.2,  # Явная скорость основания
        v_plecha=0.15,  # Явная скорость плеча
        v_strely=0.1,  # Явная скорость стрелы
        velocity_factor=0.2,
        acceleration_factor=0.2
    )
    time.sleep(3)
    print("   ✅ Движение с заданными скоростями завершено")

    print("\n✅ Серия движений по углам завершена!")


def move_by_coordinates(manipulator):
    """
    Перемещение по декартовым координатам (обновлено для SDK 0.6.8)
    Теперь с использованием точных координат
    """
    print("\n" + "=" * 60)
    print("📍 ПЕРЕМЕЩЕНИЕ ПО КООРДИНАТАМ (SDK 0.6.8)")
    print("=" * 60)

    # Используем точные координаты (рекомендация SDK 0.6.8)
    print("\n💡 Используем точные координаты для избежания ошибок планирования")

    # Движение 1: Точная стартовая позиция
    print("\n1. Движение в точную стартовую позицию")
    position = MoveCoordinatesParamsPosition(
        x=0.2279991579119544,
        y=-0.25677241023135805,
        z=0.24713621034095856
    )
    orientation = MoveCoordinatesParamsOrientation(x=0, y=0, z=0, w=1.0)
    manipulator.move_to_coordinates(
        position=position,
        orientation=orientation,
        velocity_scaling_factor=0.2,
        acceleration_scaling_factor=0.2,
        planner_type=PlannerType.LIN
    )
    time.sleep(3)
    print("   ✅ Точная позиция достигнута")

    # Движение 2-4: Стандартные движения
    movements = [
        ("2. Движение влево", 0.3, 0.1, 0.25),
        ("3. Движение вправо", 0.3, -0.1, 0.25),
        ("4. Движение вверх", 0.3, 0.0, 0.35)
    ]

    for description, x, y, z in movements:
        print(f"\n{description}")
        position = MoveCoordinatesParamsPosition(x=x, y=y, z=z)
        manipulator.move_to_coordinates(
            position=position,
            orientation=orientation,
            velocity_scaling_factor=0.2
        )
        time.sleep(3)
        print(f"   ✅ Позиция достигнута")

    print("\n✅ Серия движений по координатам завершена!")


def stream_velocities(manipulator):
    """
    Стриминг скоростей (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("🌊 СТРИМИНГ СКОРОСТЕЙ (TWIST)")
    print("=" * 60)

    print("\n1. Включение режима TWIST...")
    manipulator.set_servo_twist_mode()
    time.sleep(1)
    print("   ✅ Режим TWIST активирован")

    print("\n2. Движение вперед (10 шагов)")
    for i in range(10):
        linear_vel = {"x": 0.02, "y": 0, "z": 0}
        angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
        time.sleep(0.1)
        if i % 3 == 0:
            print(f"   Шаг {i + 1}/10")
    print("   ✅ Движение завершено")

    # Остановка
    linear_vel = {"x": 0, "y": 0, "z": 0}
    angular_vel = {"rx": 0, "ry": 0, "rz": 0}
    manipulator.stream_cartesian_velocities(linear_vel, angular_vel)

    print("\n✅ Стриминг скоростей завершен!")


def stream_pose(manipulator):
    """
    Стриминг позы (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("🎨 СТРИМИНГ ПОЗЫ (POSE)")
    print("=" * 60)

    print("\n1. Включение режима POSE...")
    manipulator.set_servo_pose_mode()
    time.sleep(1)
    print("   ✅ Режим POSE активирован")

    print("\n2. Рисование квадрата (20 точек)")
    start_x, start_y, start_z = 0.27, 0.0, 0.2
    side_length = 0.05
    orientation = MoveCoordinatesParamsOrientation(x=0, y=0, z=0, w=1)

    points = []
    for i in range(5):
        points.append((start_x, start_y + (side_length / 4) * i, start_z))
    for i in range(5):
        points.append((start_x - (side_length / 4) * i, start_y + side_length, start_z))
    for i in range(5):
        points.append((start_x - side_length, start_y + side_length - (side_length / 4) * i, start_z))
    for i in range(5):
        points.append((start_x - side_length + (side_length / 4) * i, start_y, start_z))

    for idx, (x, y, z) in enumerate(points):
        position = MoveCoordinatesParamsPosition(x=x, y=y, z=z)
        manipulator.stream_coordinates(position, orientation)
        time.sleep(0.1)
        if idx % 5 == 0:
            print(f"   Точка {idx + 1}/{len(points)}")

    print("   ✅ Квадрат нарисован")
    print("\n✅ Стриминг позы завершен!")


def gripper_control(manipulator):
    """
    Управление гриппером (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("✋ УПРАВЛЕНИЕ ГРИППЕРОМ")
    print("=" * 60)

    print("\n1. Включение питания насадки...")
    manipulator.nozzle_power(True)
    time.sleep(1)

    print("\n2. Открытие гриппера (gripper=50°)")
    manipulator.manage_gripper(rotation=0, gripper=50)
    time.sleep(2)

    print("\n3. Полное закрытие - захват (gripper=10°)")
    manipulator.manage_gripper(rotation=0, gripper=10)
    time.sleep(2)

    print("\n4. Поворот гриппера (rotation=45°)")
    manipulator.manage_gripper(rotation=45, gripper=10)
    time.sleep(2)

    print("\n5. Открытие - отпускание (gripper=50°)")
    manipulator.manage_gripper(rotation=0, gripper=50)
    time.sleep(2)

    print("\n6. Выключение питания...")
    manipulator.nozzle_power(False)

    print("\n✅ Тест гриппера завершен!")


def get_current_coordinates(manipulator):
    """
    Получение текущих координат (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("📊 ПОЛУЧЕНИЕ ТЕКУЩИХ КООРДИНАТ")
    print("=" * 60)

    print("\n1. Запрос текущих координат...")
    coords = manipulator.get_cartesian_coordinates()

    print("\n📍 Текущая позиция:")
    print(f"   X: {coords.get('x', 0):.4f} м")
    print(f"   Y: {coords.get('y', 0):.4f} м")
    print(f"   Z: {coords.get('z', 0):.4f} м")

    print("\n🔧 Углы суставов:")
    joints = manipulator.get_joint_state()
    print(f"   Основание: {joints.get('povorot_osnovaniya', 0):.4f} рад")
    print(f"   Плечо: {joints.get('privod_plecha', 0):.4f} рад")
    print(f"   Стрела: {joints.get('privod_strely', 0):.4f} рад")

    print("\n✅ Данные получены!")


def get_home_position(manipulator):
    """
    Получение домашней позиции (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("🏠 ПОЛУЧЕНИЕ ДОМАШНЕЙ ПОЗИЦИИ")
    print("=" * 60)

    print("\n1. Запрос домашней позиции...")
    home_pos = manipulator.get_home_position()

    print("\n🏠 Домашняя позиция:")
    print(f"   Основание: {home_pos.get('povorot_osnovaniya', 0):.4f} рад")
    print(f"   Плечо: {home_pos.get('privod_plecha', 0):.4f} рад")
    print(f"   Стрела: {home_pos.get('privod_strely', 0):.4f} рад")

    print("\n✅ Домашняя позиция получена!")


def move_to_home(manipulator):
    """
    Перемещение в домашнюю позицию (обновлено для SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("🏠 ПЕРЕМЕЩЕНИЕ В ДОМАШНЮЮ ПОЗИЦИЮ (SDK 0.6.8)")
    print("=" * 60)

    print("\n1. Получение домашней позиции...")
    home = manipulator.get_home_position()

    print("\n2. Перемещение домой с новыми параметрами...")
    manipulator.move_to_angles(
        povorot_osnovaniya=home.get('povorot_osnovaniya', 0),
        privod_plecha=home.get('privod_plecha', 0),
        privod_strely=home.get('privod_strely', 0),
        v_osnovaniya=0.0,
        v_plecha=0.0,
        v_strely=0.0,
        velocity_factor=0.15,  # Умеренная скорость
        acceleration_factor=0.15
    )
    time.sleep(3)
    print("   ✅ Домашняя позиция достигнута")

    print("\n✅ Возврат домой завершен!")


def subscribe_joints_and_move(manipulator):
    """
    ОБНОВЛЕНО для SDK 0.6.8
    Подписка на состояние СУСТАВОВ + движение

    ⚠️ В SDK 0.6.8 для MEdu есть только подписка на суставы:
    - subscribe_to_joint_state() ✅
    - subscribe_coordinates() ❌ (удалена)
    """
    print("\n" + "=" * 60)
    print("📡 ПОДПИСКА НА СУСТАВЫ + ДВИЖЕНИЕ (SDK 0.6.8)")
    print("=" * 60)

    update_count = [0]
    joints_history = []

    def joints_callback(data):
        """Callback для подписки на суставы"""
        update_count[0] += 1
        joints_history.append({
            'povorot_osnovaniya': data.get('povorot_osnovaniya', 0),
            'privod_plecha': data.get('privod_plecha', 0),
            'privod_strely': data.get('privod_strely', 0),
            'time': time.time()
        })

        if update_count[0] % 5 == 0:
            print(f"   🔧 Обновление {update_count[0]}: "
                  f"Основание={data.get('povorot_osnovaniya', 0):.3f}, "
                  f"Плечо={data.get('privod_plecha', 0):.3f}, "
                  f"Стрела={data.get('privod_strely', 0):.3f}")

    # Подписываемся
    print("\n1. Подписка на состояние суставов...")
    manipulator.subscribe_to_joint_state(callback=joints_callback)
    time.sleep(2)
    print(f"   ✅ Подписка активна (получено обновлений: {update_count[0]})")

    # Выполняем движения
    print("\n2. Начало движения (суставы будут обновляться)...")

    movements = [
        ("Движение 1", 0.5, -0.3, -0.5),
        ("Движение 2", -0.3, -0.5, -0.7),
        ("Движение 3", 0.0, 0.0, 0.0)
    ]

    for name, p1, p2, p3 in movements:
        print(f"\n   {name}...")
        manipulator.move_to_angles(
            povorot_osnovaniya=p1,
            privod_plecha=p2,
            privod_strely=p3,
            v_osnovaniya=0.0,
            v_plecha=0.0,
            v_strely=0.0,
            velocity_factor=0.15,
            acceleration_factor=0.15
        )
        time.sleep(4)
        print(f"   ✅ {name} завершено (обновлений: {update_count[0]})")

    # Отписываемся
    print("\n3. Отписка от суставов...")
    manipulator.unsubscribe_from_joint_state()
    time.sleep(1)

    # Статистика
    print(f"\n4. Статистика:")
    print(f"   Всего обновлений: {update_count[0]}")
    print(f"   Записано в историю: {len(joints_history)}")

    print("\n✅ Тест подписки на суставы завершен!")


def track_coordinates_polling(manipulator):
    """
    НОВАЯ ФУНКЦИЯ для SDK 0.6.8
    Альтернатива подписке: опрос координат в цикле

    ⚠️ Поскольку subscribe_coordinates() удалена,
    используем периодический опрос get_cartesian_coordinates()
    """
    print("\n" + "=" * 60)
    print("📍 ОТСЛЕЖИВАНИЕ КООРДИНАТ ЧЕРЕЗ ОПРОС (SDK 0.6.8)")
    print("=" * 60)
    print("💡 Альтернатива подписке: опрос координат каждые 100 мс")

    coords_history = []
    stop_tracking = [False]

    def tracking_thread():
        """Поток для опроса координат"""
        while not stop_tracking[0]:
            try:
                coords = manipulator.get_cartesian_coordinates()
                coords_history.append({
                    'x': coords.get('x', 0),
                    'y': coords.get('y', 0),
                    'z': coords.get('z', 0),
                    'time': time.time()
                })

                if len(coords_history) % 10 == 0:
                    print(f"   📍 Опрос {len(coords_history)}: "
                          f"X={coords.get('x', 0):.3f}, "
                          f"Y={coords.get('y', 0):.3f}, "
                          f"Z={coords.get('z', 0):.3f}")
            except Exception as e:
                print(f"   ⚠️ Ошибка опроса: {e}")

            time.sleep(0.1)  # Опрос каждые 100 мс (10 Гц)

    # Запускаем отслеживание
    print("\n1. Запуск отслеживания координат...")
    thread = threading.Thread(target=tracking_thread, daemon=True)
    thread.start()
    time.sleep(2)
    print(f"   ✅ Отслеживание активно (записей: {len(coords_history)})")

    # Выполняем движения
    print("\n2. Движение с отслеживанием координат...")

    movements = [
        ("в точку 1", 0.3, 0.05, 0.25),
        ("в точку 2", 0.25, -0.05, 0.3),
        ("в точку 3", 0.32, 0.0, 0.2)
    ]

    for name, x, y, z in movements:
        print(f"\n   Движение {name}...")
        position = MoveCoordinatesParamsPosition(x=x, y=y, z=z)
        orientation = MoveCoordinatesParamsOrientation(x=0, y=0, z=0, w=1.0)
        manipulator.move_to_coordinates(
            position=position,
            orientation=orientation,
            velocity_scaling_factor=0.15
        )
        time.sleep(4)
        print(f"   ✅ Достигнута (записей: {len(coords_history)})")

    # Останавливаем отслеживание
    print("\n3. Остановка отслеживания...")
    stop_tracking[0] = True
    time.sleep(0.5)

    # Статистика
    print(f"\n4. Статистика отслеживания:")
    print(f"   Всего записей: {len(coords_history)}")
    print(f"   Частота опроса: ~10 Гц (каждые 100 мс)")

    if len(coords_history) >= 2:
        first = coords_history[0]
        last = coords_history[-1]
        print(f"\n   Первая запись: X={first['x']:.3f}, Y={first['y']:.3f}, Z={first['z']:.3f}")
        print(f"   Последняя запись: X={last['x']:.3f}, Y={last['y']:.3f}, Z={last['z']:.3f}")

    print("\n✅ Отслеживание координат завершено!")


def gpio_blink(manipulator):
    """
    Моргание светодиодом (без изменений в SDK 0.6.8)
    """
    print("\n" + "=" * 60)
    print("💡 МОРГАНИЕ СВЕТОДИОДОМ (GPIO)")
    print("=" * 60)

    def set_led(state):
        manipulator.write_gpio(
            name=GPIO_LED_PIN,
            value=1 if state else 0,
            timeout_seconds=0.5,
            throw_error=False
        )

    print("\n1. Тест включения/выключения:")
    print("   💡 Включение...")
    set_led(True)
    time.sleep(2)
    print("   ⚫ Выключение...")
    set_led(False)
    time.sleep(2)

    print("\n2. Медленное моргание (1 Гц, 5 циклов):")
    for i in range(5):
        print(f"   Цикл {i + 1}/5: 💡 ВКЛ", end="", flush=True)
        set_led(True)
        time.sleep(0.5)
        print(" → ⚫ ВЫКЛ")
        set_led(False)
        time.sleep(0.5)

    print("\n3. Быстрое моргание (2 Гц, 10 циклов):")
    for i in range(10):
        set_led(True)
        time.sleep(0.25)
        set_led(False)
        time.sleep(0.25)
        if (i + 1) % 3 == 0:
            print(f"   Цикл {i + 1}/10 завершен")

    set_led(False)
    print("\n✅ Тест GPIO завершен!")


def gpio_read_test(manipulator):
    """
    НОВАЯ ФУНКЦИЯ для SDK 0.6.8
    Тест чтения GPIO
    """
    print("\n" + "=" * 60)
    print("📖 ЧТЕНИЕ GPIO (НОВОЕ В SDK 0.6.8)")
    print("=" * 60)

    print("\n1. Чтение текущего состояния GPIO...")
    try:
        value = manipulator.get_gpio_value(
            name=GPIO_LED_PIN,
            timeout_seconds=5.0,
            throw_error=True
        )
        print(f"   📍 Текущее значение: {value}")
        print(f"   {'💡 LED включен' if value == 1 else '⚫ LED выключен'}")
    except Exception as e:
        print(f"   ❌ Ошибка чтения: {e}")

    print("\n2. Цикл записи и чтения:")
    for state in [True, False, True, False]:
        # Запись
        print(f"\n   Установка LED: {'💡 ВКЛ' if state else '⚫ ВЫКЛ'}")
        manipulator.write_gpio(GPIO_LED_PIN, 1 if state else 0, timeout_seconds=0.5, throw_error=False)
        time.sleep(0.5)

        # Чтение
        try:
            read_value = manipulator.get_gpio_value(GPIO_LED_PIN, timeout_seconds=2.0, throw_error=False)
            expected = 1 if state else 0
            status = "✅" if read_value == expected else "❌"
            print(f"   {status} Прочитано: {read_value} (ожидалось: {expected})")
        except Exception as e:
            print(f"   ❌ Ошибка чтения: {e}")

    # Выключаем
    manipulator.write_gpio(GPIO_LED_PIN, 0, timeout_seconds=0.5, throw_error=False)

    print("\n✅ Тест чтения GPIO завершен!")


def play_audio_test(manipulator):
    """
    НОВАЯ ФУНКЦИЯ для SDK 0.6.8
    Тест воспроизведения аудио
    """
    print("\n" + "=" * 60)
    print("🎵 ВОСПРОИЗВЕДЕНИЕ АУДИО (НОВОЕ В SDK 0.6.8)")
    print("=" * 60)

    print("\n⚠️  Для работы аудиофайл должен быть загружен на манипулятор")

    audio_files = [
        "start.wav",
        "notification.wav",
        "complete.mp3"
    ]

    print("\n1. Попытка воспроизведения аудиофайлов:")
    for audio_file in audio_files:
        print(f"\n   🎵 Воспроизведение: {audio_file}")
        try:
            manipulator.play_audio(
                file_name=audio_file,
                timeout_seconds=10.0,
                throw_error=True
            )
            print(f"   ✅ Файл {audio_file} воспроизведен")
            time.sleep(1)
        except Exception as e:
            print(f"   ⚠️ Файл {audio_file} недоступен: {e}")

    print("\n💡 Если файлы не найдены, загрузите их на манипулятор")
    print("   Поддерживаемые форматы: WAV, MP3")

    print("\n✅ Тест аудио завершен!")


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """
    Главная функция
    Раскомментируйте нужную функцию для выполнения
    """
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

    # Подключение к манипулятору
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
        # ===== ОБНОВЛЕННЫЕ ФУНКЦИИ (SDK 0.6.8) =====

        # 1. Движения по углам (ОБНОВЛЕНО - новые параметры)
        # move_by_angles(manipulator)

        # 2. Движения по координатам (ОБНОВЛЕНО - точные координаты)
        # move_by_coordinates(manipulator)

        # 3. Перемещение домой (ОБНОВЛЕНО - новые параметры)
        # move_to_home(manipulator)

        # 4. Подписка на суставы + движение (ОБНОВЛЕНО - только суставы)
        # subscribe_joints_and_move(manipulator)

        # ===== НОВЫЕ ФУНКЦИИ (SDK 0.6.8) =====

        # 5. Отслеживание координат через опрос (НОВОЕ - альтернатива подписке)
        # track_coordinates_polling(manipulator)

        # 6. Чтение GPIO (НОВОЕ)
        gpio_read_test(manipulator)

        # 7. Воспроизведение аудио (НОВОЕ)
        # play_audio_test(manipulator)

        # ===== БЕЗ ИЗМЕНЕНИЙ =====

        # 8. Стриминг скоростей
        # stream_velocities(manipulator)

        # 9. Стриминг позы
        # stream_pose(manipulator)

        # 10. Гриппер
        # gripper_control(manipulator)

        # 11. Получение координат
        # get_current_coordinates(manipulator)

        # 12. Получение домашней позиции
        # get_home_position(manipulator)

        # 13. GPIO моргание
        # gpio_blink(manipulator)

        print("\n⚠️  Ни одна функция не выбрана!")
        print("Раскомментируйте нужную функцию в main()")
        print("\n💡 НОВЫЕ в SDK 0.6.8:")
        print("   - track_coordinates_polling() - отслеживание координат")
        print("   - gpio_read_test() - чтение GPIO")
        print("   - play_audio_test() - воспроизведение аудио")

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
