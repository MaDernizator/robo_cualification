# play_saved_points.py
import json
import time
from pathlib import Path
from typing import Tuple, Dict, Any

from sdk.manipulators.medu import MEdu
from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
    PlannerType,
)

HOST = "172.16.2.190"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "cells-calib-001"

COORDS_FILE = Path("coords3.json")

# Параметры траектории (скейлы <0..1>)
VELOCITY_SCALE = 0.2
ACCEL_SCALE = 0.2
PLANNER = PlannerType.PTP  # или PlannerType.LINEAR при необходимости

# Пауза между точками (сек), если нужна визуальная «ступенька»
DWELL_BETWEEN_POINTS = 0.0


def pose_to_params(pose: Dict[str, Any]) -> Tuple[MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation]:
    """
    Приводит словарь позы (как вернул get_cartesian_coordinates) к параметрам MoveCoordinates*.
    Ожидается структура:
      {
        "position": {"x": ..., "y": ..., "z": ...},
        "orientation": {"x": ..., "y": ..., "z": ..., "w": ...}
      }
    Допущение: если 'position'/'orientation' нет, пробуем взять плоские ключи.
    """
    if isinstance(pose, str):
        pose = json.loads(pose)

    if "position" in pose and "orientation" in pose:
        p = pose["position"]
        o = pose["orientation"]
        pos = MoveCoordinatesParamsPosition(float(p["x"]), float(p["y"]), float(p["z"]))
        ori = MoveCoordinatesParamsOrientation(float(o["x"]), float(o["y"]), float(o["z"]), float(o["w"]))
        return pos, ori

    # Фоллбек: плоские ключи
    keys = set(pose.keys())
    if {"x", "y", "z", "w"}.issubset(keys):
        pos = MoveCoordinatesParamsPosition(float(pose["x"]), float(pose["y"]), float(pose["z"]))
        ori = MoveCoordinatesParamsOrientation(float(pose["x"]), float(pose["y"]), float(pose["z"]), float(pose["w"]))
        return pos, ori

    if {"x", "y", "z", "qx", "qy", "qz", "qw"}.issubset(keys):
        pos = MoveCoordinatesParamsPosition(float(pose["x"]), float(pose["y"]), float(pose["z"]))
        ori = MoveCoordinatesParamsOrientation(float(pose["qx"]), float(pose["qy"]), float(pose["qz"]), float(pose["qw"]))
        return pos, ori

    raise ValueError(f"Неподдерживаемый формат позы: {pose}")


def rotate_gripper(manip: MEdu, angle_deg: int, power_on: bool = True, power_off_after: bool = False) -> None:
    """
    Вращение захвата (насадки) на заданный угол в градусах.
    Для работы требуется питание на разъёмах стрелы.
    """
    if power_on:
        manip.nozzle_power(True)
    manip.manage_gripper(rotation=int(angle_deg))
    if power_off_after:
        manip.nozzle_power(False)


def main():
    print("=== Проход по сохранённым точкам ===")

    if not COORDS_FILE.exists():
        raise FileNotFoundError(f"Файл с точками не найден: {COORDS_FILE.resolve()}")

    saved = json.loads(COORDS_FILE.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or not saved:
        raise ValueError(f"В {COORDS_FILE} нет валидных точек.")

    # Порядок dict сохранится таким, как был записан в coords3.json
    points = list(saved.items())
    print(f"[*] Найдено точек: {len(points)}")

    manip = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    print("[*] Подключаемся…")
    manip.connect()
    print("[+] Подключено.")

    try:
        manip.get_control()
        print("[+] Получено управление манипулятором.")

        for i, (name, pose) in enumerate(points, start=1):
            try:
                pos, ori = pose_to_params(pose)
            except Exception as e:
                print(f"[!] Пропуск «{name}»: не удалось разобрать позу ({e})")
                continue

            print(f"\n[{i}/{len(points)}] Едем в «{name}» ...")
            manip.move_to_coordinates(
                pos,
                ori,
                VELOCITY_SCALE,
                ACCEL_SCALE,
                PLANNER,
                timeout_seconds=60.0,
                throw_error=True,
            )
            print(f"    [✓] Достигнута «{name}»")

            if DWELL_BETWEEN_POINTS > 0:
                time.sleep(DWELL_BETWEEN_POINTS)

        print("\n[✓] Маршрут завершён.")

        # Пример использования вращения захвата (по необходимости):
        # rotate_gripper(manip, angle_deg=45)  # раскомментируйте для теста

    finally:
        try:
            manip.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
