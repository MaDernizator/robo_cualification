from sdk.manipulators.medu import MEdu

# Подключение к MEdu манипулятору
manipulator = MEdu(
    host="10.5.0.2",  # IP адрес манипулятора
    client_id="client_1",
    login="user",
    password="pass"
)

# Подключение
manipulator.connect()

# Получение управления
manipulator.get_control()

# функция которая поворачивает руку влево вправо при заданых других углах поворота
# manipulator - объект руки, speed - скорость движениея, angle - угол поворота вокруг основания
def move_to_angles(manipulator : MEdu, speed : float, angle : float):
    manipulator.move_to_angles(
        povorot_osnovaniya=angle,   # Угол поворота основания (радианы)
        privod_plecha=-0.5,       # Угол плеча (радианы)
        privod_strely=-0.8,       # Угол стрелы (радианы)
        v_osnovaniya=0.0,         # Скорость основания (рад/с)
        v_plecha=0.0,             # Скорость плеча (рад/с)
        v_strely=0.0,             # Скорость стрелы (рад/с)
        velocity_factor=speed,    # Множитель скорости 0.0-1.0
        acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
        timeout_seconds=60.0,     # Таймаут выполнения
        throw_error=True          # Бросать исключение при ошибке
    )

move_to_angles(manipulator, 1, 1) # движение на старт

# проход справа на лево
move_to_angles(manipulator, 0.7, 0.1) # прохождение крайней зоны
move_to_angles(manipulator, 0.3, 0.3) # прохождение средней зоны
move_to_angles(manipulator, -0.3, 0.8) # прохождение центральной зоны
move_to_angles(manipulator, -0.7, 0.3) # прохождение средней зоны
move_to_angles(manipulator, -1, 0.1) # прохождение крайней зоны

# возвращение в начало
move_to_angles(manipulator, -0.7, 0.1) # прохождение крайней зоны
move_to_angles(manipulator, -0.3, 0.3) # прохождение средней зоны
move_to_angles(manipulator, 0.3, 0.8) # прохождение центральной зоны
move_to_angles(manipulator, 0.7, 0.3) # прохождение средней зоны
move_to_angles(manipulator, 1, 0.1) # прохождение крайней зоны

# Отключение
manipulator.disconnect()