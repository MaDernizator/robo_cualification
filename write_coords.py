#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

from sdk.manipulators.medu import MEdu  # если другой манипулятор — замените
from sdk.utils.constants import CARTESIAN_COORDINATES_TOPIC  # просто для справки

HOST = "172.16.2.190"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "cells-calib-001"


OUTPUT_FILE = Path("coords3.json")
CELL_NAMES = ["CELL_1", "CELL_2", "CELL_3", "CELL_4", "BUFFER"]
# CELL_NAMES = ["BUFFER"]

def main():
    print("=== Калибровка: FreeDrive → Enter для сохранения точки ===")

    manip = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    print("[*] Подключаемся…")
    manip.connect()
    print("[+] Подключено.")

    saved = {}
    try:
        for name in CELL_NAMES:
            input(f"\nНаведите TCP в центр «{name}» и нажмите Enter…")

            # Синхронно получить последнюю кардио (SDK сам подпишется на /coordinates)
            payload = manip.get_cartesian_coordinates(timeout_seconds=5.0)
            # payload приходит как JSON-строка; распарсим
            pose = json.loads(payload) if isinstance(payload, str) else payload

            saved[name] = pose
            print(f"   [+] {name}: {pose}")

        OUTPUT_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[✓] Готово. Сохранено {len(saved)} точек в {OUTPUT_FILE.resolve()}")

    finally:
        try:
            manip.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    main()