import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
)
from sdk.manipulators.medu import MEdu

# ===================== КОНФИГУРАЦИЯ =====================

HOST = "192.168.0.183"
CLIENT_ID = "test-client"
LOGIN = "user"
PASSWORD = "pass"

COORDS_FILE = Path("coords3.json")

CELL_DESCENT_ROT = -5.0  # градусы, перед спуском в любую CELL_*
BUFFER_DESCENT_ROT = -11.0  # градусы, перед спуском в BUFFER/BUFF

# Положение "открыть/закрыть" для механического захвата
GRIP_OPEN_ANGLE = 15
GRIP_CLOSE_ANGLE = 45
GRIP_ROTATION = 0

# Профиль движения
VEL = 0.2
ACC = 0.2

# Дополнительные действия с захватом при обходе точек
SEQUENCE_GRIP_ACTIONS: Dict[str, Dict[str, float]] = {
    "p3": {"rotation": 0.0, "angle": 10.0},
    "p5": {"rotation": 80.0, "angle": 10.0},
    "B": {"rotation": -10.0, "angle": 10.0},
}

CoordinatesData = Dict[str, Dict[str, Dict[str, Any]]]


# ===================== УТИЛИТЫ =====================

def safe_sdk_call(
        description: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
) -> Any:
    """
    Универсальный обёртка для внешних вызовов SDK.
    Логирует ошибку и пробрасывает исключение дальше.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        print(f"[!] Ошибка {description}: {exc}")
        raise


def load_coordinates(path: Path) -> CoordinatesData:
    """
    Читает и валидирует JSON с координатами.
    """
    if not path.exists():
        print(f"[!] Файл с координатами не найден: {path}")
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        print(f"[!] Некорректный JSON в {path}: {exc}")
        sys.exit(1)
    except OSError as exc:
        print(f"[!] Не удалось прочитать {path}: {exc}")
        sys.exit(1)

    if not isinstance(data, dict):
        print(f"[!] Ожидался словарь верхнего уровня в {path}")
        sys.exit(1)

    return data


COORDS: CoordinatesData = load_coordinates(COORDS_FILE)


def _get_pose_from_coords(point_name: str, tool: str) -> Dict[str, Dict[str, float]]:
    """
    Достаёт позицию и ориентацию из COORDS.
    """
    try:
        point_data = COORDS[point_name][tool]
        position = point_data["position"]
        orientation = point_data["orientation"]
    except KeyError as exc:
        raise KeyError(
            f"В файле {COORDS_FILE} нет точки '{point_name}' и/или инструмента '{tool}'"
        ) from exc

    return {"position": position, "orientation": orientation}


# ===================== НИЗКОУРОВНЕВЫЕ ДВИЖЕНИЯ =====================

def move(
        manipulator: MEdu,
        x: float,
        y: float,
        z: float,
        ox: float,
        oy: float,
        oz: float,
        ow: float,
        velocity: float = VEL,
        acceleration: float = ACC,
        *,
        timeout: float = 60.0,
) -> None:
    """
    Блокирующий move: ждём завершения траектории, чтобы
    следующая команда не «съела» промежуточную точку.
    """
    promise = safe_sdk_call(
        "при отправке команды move_to_coordinates",
        manipulator.move_to_coordinates,
        MoveCoordinatesParamsPosition(x=x, y=y, z=z),
        MoveCoordinatesParamsOrientation(x=ox, y=oy, z=oz, w=ow),
        velocity_scaling_factor=velocity,
        acceleration_scaling_factor=acceleration,
    )

    if hasattr(promise, "result"):
        safe_sdk_call(
            "при ожидании завершения движения",
            promise.result,
            timeout=timeout,
        )
    else:
        time.sleep(0.2)


def move_pose(
        manipulator: MEdu,
        point_name: str,
        tool: str = "tool0",
        velocity: float = VEL,
        acceleration: float = ACC,
) -> None:
    """
    Перемещает манипулятор в точку из COORDS.
    """
    pose = _get_pose_from_coords(point_name, tool)
    position = pose["position"]
    orientation = pose["orientation"]

    move(
        manipulator,
        x=position["x"],
        y=position["y"],
        z=position["z"],
        ox=orientation["x"],
        oy=orientation["y"],
        oz=orientation["z"],
        ow=orientation["w"],
        velocity=velocity,
        acceleration=acceleration,
    )


def _set_gripper(manipulator: MEdu, rotation: float, angle: int) -> None:
    """
    Низкоуровневое управление захватом с логированием ошибок.
    """
    safe_sdk_call(
        "при управлении захватом",
        manipulator.manage_gripper,
        rotation=rotation,
        gripper=angle,
    )


def apply_sequence_gripper_action(manipulator: MEdu, point_name: str) -> None:
    """
    Применяет преднастроенное действие с захватом для точки, если оно есть.
    """
    config = SEQUENCE_GRIP_ACTIONS.get(point_name)
    if not config:
        return

    rotation = float(config["rotation"])
    angle = int(config["angle"])
    _set_gripper(manipulator, rotation=rotation, angle=angle)


# ===================== СЕТАП =====================

def start(
        host: str,
        client_id: str,
        login: str,
        password: str,
) -> MEdu:
    """
    Подключение к манипулятору и базовая инициализация.
    """
    manipulator = MEdu(host, client_id, login, password)

    print("[*] Подключение к манипулятору...")
    safe_sdk_call("при подключении", manipulator.connect)

    print("[*] Запрашиваем управление...")
    safe_sdk_call("при получении управления", manipulator.get_control)

    print("[*] Подаём питание на насадку...")
    safe_sdk_call("при подаче питания на насадку", manipulator.nozzle_power, True)

    time.sleep(0.2)

    print("[+] Манипулятор готов к работе")
    return manipulator


def end(manipulator: MEdu) -> None:
    """
    Завершение работы с манипулятором.
    """
    try:
        safe_sdk_call("при отключении питания насадки", manipulator.nozzle_power, False)
    except Exception:
        pass

    try:
        safe_sdk_call("при освобождении управления", manipulator.release_control)
    except Exception:
        pass

    try:
        safe_sdk_call("при отключении от манипулятора", manipulator.disconnect)
    except Exception:
        pass


# ===================== ОБХОД ТОЧЕК =====================

def traverse_points_from_coords(manipulator: MEdu) -> None:
    """
    Последовательно обходит все точки из coords3.json
    в порядке, указанном в файле.
    Для некоторых точек дополнительно управляет захватом.
    """
    print("[=] Обход точек в порядке, как они идут в coords3.json:")

    for name, tools in COORDS.items():
        apply_sequence_gripper_action(manipulator, name)

        if "tool0" not in tools:
            print(f"[!] Для точки '{name}' нет координат tool0, точка пропущена")
            continue

        print(f"  -> {name}.tool0")
        move_pose(manipulator, name, "tool0")

    print("[✓] Обход всех точек завершён")


# ===================== MAIN =====================

def main() -> None:
    manipulator: Optional[MEdu] = None

    try:
        manipulator = start(HOST, CLIENT_ID, LOGIN, PASSWORD)
        traverse_points_from_coords(manipulator)
        print("Готово")
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
    except Exception as exc:
        print(f"Некритичная ошибка верхнего уровня: {exc}")
    finally:
        if manipulator is not None:
            end(manipulator)


if __name__ == "__main__":
    main()
