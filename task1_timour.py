from sdk.manipulators.medu import MEdu

class PromobotManipulator:
    # Подключение к MEdu манипулятору
    def __init__(self, 
                 host: str  # IP адрес манипулятора
                 ):
        self._manipulator = MEdu(
            host=host,
            client_id="client_1",
            login="user",
            password="pass"
        )

        self._is_connected = False
        self._is_controlled = False

    # Подключение
    def connect(self):
        if not self._is_connected:
            self._manipulator.connect()
            self._manipulator.nozzle_power(True)   # Включаем питание моторов
            self._is_connected = True

    # Получение управления
    def get_control(self):
        if not self._is_connected:
            self.connect()
        if not self._is_controlled:
            self._manipulator.get_control()
            self._is_controlled = True

    
    # функция которая поворачивает руку влево вправо при статичных заданных других углах поворота
    def move_to_angles(self,
                       speed: float, # скорость движениея 0.0-1.0
                       angle: float  # угол поворота вокруг основания
                       ):
        if not self._is_connected:
            self.connect()
        if not self._is_controlled:
            self.get_control()

        self._manipulator.move_to_angles(
            povorot_osnovaniya=angle,   # Угол поворота основания (радианы)
            privod_plecha=-0.5,         # Угол плеча (радианы)
            privod_strely=-0.8,         # Угол стрелы (радианы)
            v_osnovaniya=0.0,           # Скорость основания (рад/с)
            v_plecha=0.0,               # Скорость плеча (рад/с)
            v_strely=0.0,               # Скорость стрелы (рад/с)
            velocity_factor=speed,      # Множитель скорости 0.0-1.0
            acceleration_factor=0.1,    # Множитель ускорения 0.0-1.0
            timeout_seconds=60.0,       # Таймаут выполнения
            throw_error=True            # Бросать исключение при ошибке
        )
    
    # Отключение
    def disconnect(self):
        if self._is_connected:
            self._manipulator.disconnect()
            self._is_connected = False
            self._is_controlled = False

    # деструктор: Автоматический вызов при удалении объекта
    def __del__(self):
        self.disconnect()

# ===========================
# ЗАПУСК 1 задания
# ===========================

# создаём объект
manipulator = PromobotManipulator(host="10.5.0.2")

# подключаемся и получаем управление что бы дальше упровлять рукой
manipulator.connect()
manipulator.get_control()

# движение на старт(справа)
manipulator.move_to_angles(speed=1.0, angle=1.0)

# проход справа на лево 
manipulator.move_to_angles(0.7, 0.1) # прохождение крайней зоны
manipulator.move_to_angles(0.3, 0.3) # прохождение средней зоны
manipulator.move_to_angles(-0.3, 0.8) # прохождение центральной зоны
manipulator.move_to_angles(-0.7, 0.3) # прохождение средней зоны
manipulator.move_to_angles(-1, 0.1) # прохождение крайней зоны

# возвращение в начало
manipulator.move_to_angles(-0.7, 0.1) # прохождение крайней зоны
manipulator.move_to_angles(-0.3, 0.3) # прохождение средней зоны
manipulator.move_to_angles(0.3, 0.8) # прохождение центральной зоны
manipulator.move_to_angles(0.7, 0.3) # прохождение средней зоны
manipulator.move_to_angles(1, 0.1) # прохождение крайней зоны

# отключаемся
manipulator.disconnect()