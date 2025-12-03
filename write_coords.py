import json
from pathlib import Path

from sdk.manipulators.medu import MEdu  # если другой манипулятор — замените
from sdk.utils.constants import CARTESIAN_COORDINATES_TOPIC  # просто для справки

HOST = "10.5.0.2"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "cells-calib-001"

OUTPUT_FILE = Path("coords3.json")


def safe_get_pose(manip: MEdu, timeout_seconds: float = 5.0):
    """
    Получить текущие декартовы координаты TCP.
    SDK может вернуть строку JSON или dict.
    """
    payload = manip.get_cartesian_coordinates(timeout_seconds=timeout_seconds)
    if payload is None:
        raise RuntimeError("Не удалось получить координаты: получен пустой ответ от SDK.")
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


def main():
    print("=== Калибровка: введите имя точки → наведите TCP → Enter для сохранения. Пустое имя — выход. ===")

    # Подгружаем существующие точки (если файл уже есть)
    saved = {}
    if OUTPUT_FILE.exists():
        try:
            saved = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                print("[!] Файл координат повреждён, начнём заново.")
                saved = {}
            else:
                print(f"[*] Загружено существующих точек: {len(saved)}")
        except Exception:
            print("[!] Не удалось прочитать существующий файл, начнём заново.")

    manip = MEdu(HOST, CLIENT_ID, LOGIN, PASSWORD)
    print("[*] Подключаемся…")
    manip.connect()
    print("[+] Подключено.")

    try:
        while True:
            name = input("\nВведите имя точки (Enter — завершить): ").strip()
            if not name:
                break

            if name in saved:
                print(f"[!] Точка «{name}» уже существует — будет перезаписана.")

            input(f"Наведите TCP в целевую позицию для «{name}» и нажмите Enter для сохранения…")

            try:
                pose = safe_get_pose(manip, timeout_seconds=5.0)
            except Exception as e:
                print(f"   [!] Ошибка чтения координат: {e}. Пропускаем точку «{name}».")
                continue

            saved[name] = pose
            OUTPUT_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"   [✓] Сохранено «{name}»: {pose}")
            print(f"   [*] Всего точек: {len(saved)} → файл: {OUTPUT_FILE.resolve()}")

        print(f"\n[✓] Готово. Сохранено {len(saved)} точек в {OUTPUT_FILE.resolve()}")

    finally:
        try:
            manip.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
