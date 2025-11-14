"""
Вращение J1 с адаптивной скоростью.
"""

import time
from sdk.manipulators.medu import MEdu

# === Подключение ===
HOST = "10.5.0.2"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "j1-guard-move"

# === Безопасная поза ===
SAFE_SHOULDER_ANGLE = -0.35  # J2: плечо — вверх
SAFE_ELBOW_ANGLE = -0.75  # J3: стрела — вперёд

# === Зоны скорости для J1 ===
SPEED_BY_ZONE = {
    "red": 0.10,  # Медленно в опасной зоне
    "yellow": 0.50,  # Средняя скорость в промежуточной зоне
    "green": 0.80  # Быстро в безопасной зоне
}
ZONE_BORDERS_DEGREES = [-90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0]  # Границы зон в градусах


# --- Вспомогательные функции ---

def rad2deg(radians):
    """Конвертация радианов в градусы"""
    return float(radians) * 180.0 / 3.141592653589793


def deg2rad(degrees):
    """Конвертация градусов в радианы"""
    return float(degrees) * 3.141592653589793 / 180.0


def zone_of_j1(j1_degrees):
    """Определение зоны безопасности по углу J1"""
    if abs(j1_degrees) > 112:
        return "red"  # Опасная зона
    if abs(j1_degrees) > 56:
        return "yellow"  # Промежуточная зона
    return "green"  # Безопасная зона


def nearest_border_between(angle_start, angle_end):
    """Поиск ближайшей границы зоны между двумя углами"""
    lower_angle, upper_angle = (angle_start, angle_end) if angle_start < angle_end else (angle_end, angle_start)
    borders_in_range = [border for border in ZONE_BORDERS_DEGREES if lower_angle < border < upper_angle]
    return min(borders_in_range, key=lambda border: abs(border - angle_start)) if borders_in_range else None


# --- Основной класс ---
class SpeedGuard:
    """Класс для управления движением с адаптивной скоростью"""

    def __init__(self, robot, safe_shoulder_angle, safe_elbow_angle):
        self.robot = robot
        self.safe_shoulder_angle = safe_shoulder_angle
        self.safe_elbow_angle = safe_elbow_angle

    def move_j1_guarded(self, j1_target_degrees, max_step_degrees=5.0):
        """Безопасное движение J1 к целевому углу с адаптивной скоростью"""
        # Получаем текущий угол J1 и преобразуем в градусы
        current_angles = self.robot.get_joint_angles()
        j1_current_radians = float(current_angles[0])
        j1_current_degrees = rad2deg(j1_current_radians)

        # Определяем направление движения
        direction = 1 if j1_target_degrees > j1_current_degrees else -1

        # Движемся по шагам до достижения цели
        while abs(j1_target_degrees - j1_current_degrees) > 0.5:
            # Находим ближайшую границу зоны
            nearest_border = nearest_border_between(j1_current_degrees, j1_target_degrees)

            # Вычисляем промежуточную цель (либо граница зоны, либо шаг)
            step_candidate = j1_current_degrees + direction * max_step_degrees

            if nearest_border is not None and abs(nearest_border - j1_current_degrees) < abs(
                    step_candidate - j1_current_degrees):
                subtarget_degrees = nearest_border
            else:
                subtarget_degrees = step_candidate

            # Ограничиваем промежуточную цель финальной целью
            if (direction > 0 and subtarget_degrees > j1_target_degrees) or \
                    (direction < 0 and subtarget_degrees < j1_target_degrees):
                subtarget_degrees = j1_target_degrees

            # Определяем скорость для текущей зоны
            current_zone = zone_of_j1(j1_current_degrees)
            velocity_factor = SPEED_BY_ZONE[current_zone]

            print(
                f"[J1] {j1_current_degrees:.1f}° → {subtarget_degrees:.1f}° | зона: {current_zone} | vf={velocity_factor}")

            # Выполняем движение
            self.robot.move_to_angles(
                deg2rad(subtarget_degrees),
                self.safe_shoulder_angle,
                self.safe_elbow_angle,
                velocity_factor=velocity_factor,
                acceleration_factor=0.2
            )

            # Обновляем текущую позицию
            current_angles = self.robot.get_joint_angles()
            j1_current_radians = float(current_angles[0])
            j1_current_degrees = rad2deg(j1_current_radians)

    def move_waypoints_guarded(self, j1_waypoints_degrees):
        """Последовательное движение через список точек"""
        for target_degrees in j1_waypoints_degrees:
            print(f"\n[ROUTE] → J1 = {target_degrees}°")
            self.move_j1_guarded(target_degrees)


# --- Запуск ---
def main():
    print("[INFO] Подключение...")
    manipulator = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    manipulator.connect()

    try:
        print("[INFO] Захват управления...")
        manipulator.get_control()

        # Переводим робота в исходную позу (центр)
        print("[INIT] В центр (J1=0°)...")
        manipulator.move_to_angles(0.0, SAFE_SHOULDER_ANGLE, SAFE_ELBOW_ANGLE, velocity_factor=0.3)

        # Создаем контроллер с адаптивной скоростью
        speed_guard = SpeedGuard(manipulator, SAFE_SHOULDER_ANGLE, SAFE_ELBOW_ANGLE)

        # Маршрут движения: центр → право → лево → центр
        waypoints = [90, -90, 0]

        print("\n[GO] Начало движения с адаптивной скоростью...")
        speed_guard.move_waypoints_guarded(waypoints)

        print("\nГотово!")

    except KeyboardInterrupt:
        print("\nПрервано пользователем")
    except Exception as error:
        print(f"\nОшибка: {error}")
    finally:
        try:
            manipulator.release_control()
        except:
            pass


if __name__ == "__main__":
    main()