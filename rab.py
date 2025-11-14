#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

from sdk.commands.move_coordinates_command import (
    MoveCoordinatesParamsPosition,
    MoveCoordinatesParamsOrientation,
)
from sdk.manipulators.medu import MEdu

# ===================== ПОДКЛЮЧЕНИЕ =====================

HOST = "10.5.0.2"
CLIENT_ID = "test-client"
LOGIN = "user"
PASSWORD = "pass"

COORDS_FILE = Path("coords3.json")

CELL_DESCENT_ROT = -5.0     # градусы, перед спуском в любую CELL_*
BUFFER_DESCENT_ROT = -11.0  # градусы, перед спуском в BUFFER/BUFF

# Положение "открыть/закрыть" для механического захвата (при необходимости подправь)
GRIP_OPEN_ANGLE = 15
GRIP_CLOSE_ANGLE = 45
GRIP_ROTATION = 0

# Профиль движения
VEL = 0.2
ACC = 0.2

# === КООРДИНАТЫ: ТЕПЕРЬ ИЗ coords3.json ===
try:
    with COORDS_FILE.open("r", encoding="utf-8") as f:
        data: Dict[str, Dict[str, Dict[str, Any]]] = json.load(f)
except Exception as e:
    print(f"[!] Не удалось прочитать {COORDS_FILE}: {e}")
    sys.exit(1)


# ===================== НИЗКОУРОВНЕВЫЕ ДВИЖЕНИЯ =====================

def move(m: MEdu, x: float, y: float, z: float, ox: float, oy: float, oz: float, ow: float,
         velocity: float = VEL, acceleration: float = ACC, *, timeout: float = 60.0) -> None:
    """
    Блокирующий move: ждём завершения траектории, чтобы следующая команда не «съела» промежуточную точку.
    """
    prom = m.move_to_coordinates(
        MoveCoordinatesParamsPosition(x=x, y=y, z=z),
        MoveCoordinatesParamsOrientation(x=ox, y=oy, z=oz, w=ow),
        velocity_scaling_factor=velocity,
        acceleration_scaling_factor=acceleration
    )
    # ВАЖНО: дождаться завершения
    if hasattr(prom, "result"):
        prom.result(timeout=timeout)
    else:
        # На всякий случай — минимальная задержка, если SDK вернул не-промис
        time.sleep(0.2)


def move_pose(m: MEdu, cell: str, tool: str = "tool0", v: float = VEL, a: float = ACC) -> None:
    p = data[cell][tool]["position"]
    o = data[cell][tool]["orientation"]
    move(m, p["x"], p["y"], p["z"], o["x"], o["y"], o["z"], o["w"], v, a)


def go_via_home(m: MEdu, cell: str, tool: str = "tool0", v: float = VEL, a: float = ACC) -> None:
    """Всегда поднимаемся в HOME.tool0 перед перелётом в другую точку."""
    move_pose(m, "HOME", "tool0", v, a)
    move_pose(m, cell, "tool0", v, a)  # прибываем над клеткой
    if tool == "tool1":
        move_pose(m, cell, "tool1", v, a)


def _target_rotation_for(place: str) -> float:
    """Возвращает целевой поворот кисти перед спуском в клетку/буфер."""
    name = place.upper()
    if name == "BUFFER" or name == "BUFF":
        return BUFFER_DESCENT_ROT
    if name.startswith("CELL_"):
        return CELL_DESCENT_ROT
    # на всякий случай — нейтраль
    return GRIP_ROTATION


# --- ЗАМЕНИ grab/release ТАК, ЧТОБЫ ОНИ НЕ МЕНЯЛИ ОРИЕНТАЦИЮ ПО УМОЛЧАНИЮ ---
def grab(m: MEdu, *, rotation: float = None) -> None:
    """Закрыть захват. Если rotation задан — одновременно задать поворот кисти."""
    rot = GRIP_ROTATION if rotation is None else rotation
    m.manage_gripper(rotation=rot, gripper=GRIP_CLOSE_ANGLE)


def release(m: MEdu, *, rotation: float = None) -> None:
    """Открыть захват. Если rotation задан — одновременно задать поворот кисти."""
    rot = GRIP_ROTATION if rotation is None else rotation
    m.manage_gripper(rotation=rot, gripper=GRIP_OPEN_ANGLE)


# --- pick/place: ДОБАВЛЕНА ОРИЕНТАЦИЯ ПЕРЕД СПУСКОМ ---
def pick_from(m: MEdu, cell: str) -> None:
    """Подойти над клеткой, открыться, ПОВЕРНУТЬСЯ, опуститься, схватить, подняться."""
    # Открыться и сразу выставить нужный поворот для этой точки
    r = _target_rotation_for(cell)
    release(m, rotation=r)              # открыто + нужная ориентация
    move_pose(m, cell, "tool0")         # над клеткой (страховочно)
    move_pose(m, cell, "tool1")         # вниз к кубику (уже с нужным поворотом)
    grab(m, rotation=r)                 # схватить, сохранив ориентацию
    move_pose(m, cell, "tool0")         # подняться


def place_to(m: MEdu, cell: str) -> None:
    """Подойти над клеткой, ПОВЕРНУТЬСЯ, опуститься, отпустить, подняться."""
    r = _target_rotation_for(cell)
    # Мы держим кубик закрытым — просто переустановим ориентацию, не раскрываясь
    grab(m, rotation=r)                 # подтвердить/задать поворот кисти, оставить закрытым
    move_pose(m, cell, "tool0")         # над клеткой (страховочно)
    move_pose(m, cell, "tool1")         # вниз (с нужным поворотом)
    release(m, rotation=r)              # отпустить, оставив ориентацию
    move_pose(m, cell, "tool0")         # подняться


def move_cube(m: MEdu, src_cell: str, dst_cell: str) -> None:
    """Переместить один кубик между двумя клетками/буфером, соблюдая подъём перед перелётом."""
    print(f"    - Беру из {src_cell} → кладу в {dst_cell}")
    pick_from(m, src_cell)
    place_to(m, dst_cell)


# ===================== СЕТАП/ТИДАУН =====================

def start(host: str, client_id: str, login: str, password: str) -> MEdu:
    m = MEdu(host, client_id, login, password)
    print("[*] Подключение...")
    m.connect()
    m.get_control()
    m.nozzle_power(True)
    time.sleep(0.2)
    # На старте всегда открыть «когти»
    release(m)
    print("[+] Готово к работе")
    return m


def end(m: MEdu) -> None:
    try:
        m.nozzle_power(False)
    except Exception:
        pass
    try:
        m.release_control()
    except Exception:
        pass
    try:
        m.disconnect()
    except Exception:
        pass


# ===================== СТАРЫЙ АЛГОРИТМ СОРТИРОВКИ (НЕ ИСПОЛЬЗУЕМ) =====================
# Оставлен без изменений, но теперь не вызывается, чтобы соблюдать условие задачи.

def sort_with_one_buffer_and_move(m: MEdu, A: List[int]) -> None:
    """
    A — 1-индексный список актуальной расстановки кубиков по клеткам 1..n.
    Цель: добиться A[i] == i. Доступны клетки CELL_1..CELL_n и BUFFER.
    Для минимизации перемещений используем разбор циклов перестановки:
    - из начала цикла переносим кубик в BUFFER,
    - протягиваем правильные кубики на их места по цепочке,
    - замыкаем цикл, забирая из BUFFER.
    """
    n = len(A) - 1
    # Быстрый доступ: pos[val] = где стоит кубик с номером val
    pos = [0]*(n+1)
    for i in range(1, n+1):
        pos[A[i]] = i

    for start in range(1, n+1):
        if A[start] == start:
            continue

        print(f"[ЦИКЛ] Начинаю цикл от клетки {start}: кубик {A[start]} не на месте")

        # 1) В BUFFER уводим кубик из клетки start
        buf_val = A[start]
        move_cube(m, f"CELL_{start}", "BUFFER")
        A[start] = None          # дырка появилась в start
        hole = start

        # 2) Тянем по цепочке «правильные кубики» на их места
        while True:
            need = hole  # какой номер должен стоять в дырке
            if need == buf_val:
                break  # пора замыкать цикл

            p = pos[need]            # где сейчас нужный кубик
            move_cube(m, f"CELL_{p}", f"CELL_{hole}")  # ставим его на место

            # Обновляем структуру данных
            pos[A[p]] = hole         # кубик need уехал в hole
            A[hole] = A[p]
            A[p] = None              # в p теперь дырка
            hole = p

        # 3) Замыкаем цикл: ставим кубик из BUFFER на своё целевое место (в текущую дырку)
        move_cube(m, "BUFFER", f"CELL_{hole}")
        A[hole] = buf_val
        pos[buf_val] = hole

        print(f"[ЦИКЛ] Готово: цикл, начинавшийся в {start}, закрыт")

    print("[✓] Сортировка завершена")


def parse_order(s: str) -> List[int]:
    """
    Допускаем форматы:
      - '2 3 4 1'
      - '2,3,4,1'
    """
    raw = s.replace(",", " ").split()
    nums = list(map(int, raw))
    if len(nums) != 4 or any(not (1 <= x <= 4) for x in nums):
        raise ValueError("Нужно ввести 4 числа от 1 до 4, например: 2 3 4 1")
    # Делаем 1-индексный массив A: A[i] = номер кубика в клетке i
    A = [0] + nums
    return A


# ===================== НОВЫЙ ОБХОД ТОЧЕК ИЗ coords3.json =====================

def traverse_points_from_coords(m: MEdu) -> None:
    """
    Последовательно обходим все точки из coords3.json.
    Формат ожидается такой же, как в исходном примере: name -> tool0/tool1 -> position/orientation.
    """
    names = list(data.keys())

    m.nozzle_power(True)
    print("[=] Обход точек в порядке, как они идут в coords3.json:")
    for name in names:
        if name == 'p3':
            m.manage_gripper(rotation=0, gripper=10)
        if name == 'p5':
            m.manage_gripper(rotation=80, gripper=10)
        if name == 'B':
            m.manage_gripper(rotation=-10, gripper=10)
        print(f"  -> {name}.tool0")
        if "tool0" in data[name]:
            move_pose(m, name, "tool0")

    print("[✓] Обход всех точек завершён")


# ===================== MAIN =====================

def main():
    m = None
    try:
        m = start(HOST, CLIENT_ID, LOGIN, PASSWORD)

        # Последовательный обход по точкам из coords3.json
        traverse_points_from_coords(m)

        print("[✓] Готово")

    except KeyboardInterrupt:
        print("\n[!] Прервано пользователем")
    except Exception as e:
        print("[!] Ошибка:", e)
    finally:
        if m is not None:
            end(m)


if __name__ == "__main__":
    main()
