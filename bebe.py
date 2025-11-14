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

# Движение в старт
manipulator.move_to_angles(
    povorot_osnovaniya=1,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.8,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)

manipulator.move_to_angles(
    povorot_osnovaniya=0.7,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.1,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)
manipulator.move_to_angles(
    povorot_osnovaniya=0.3,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.4,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)
manipulator.move_to_angles(
    povorot_osnovaniya=-0.3,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.8,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)
manipulator.move_to_angles(
    povorot_osnovaniya=-0.7,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.4,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)
manipulator.move_to_angles(
    povorot_osnovaniya=-1,   # Угол поворота основания (радианы)
    privod_plecha=-0.5,       # Угол плеча (радианы)
    privod_strely=-0.8,       # Угол стрелы (радианы)
    v_osnovaniya=0.0,         # Скорость основания (рад/с)
    v_plecha=0.0,             # Скорость плеча (рад/с)
    v_strely=0.0,             # Скорость стрелы (рад/с)
    velocity_factor=0.1,      # Множитель скорости 0.0-1.0
    acceleration_factor=0.1,  # Множитель ускорения 0.0-1.0
    timeout_seconds=60.0,     # Таймаут выполнения
    throw_error=True          # Бросать исключение при ошибке
)

# Отключение
manipulator.disconnect()