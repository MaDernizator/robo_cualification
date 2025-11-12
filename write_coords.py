import json
from pathlib import Path

from sdk.manipulators.medu import MEdu  # если другой манипулятор — замените
from sdk.utils.constants import CARTESIAN_COORDINATES_TOPIC  # просто для справки

HOST = "172.16.2.190"
LOGIN = "user"
PASSWORD = "pass"
CLIENT_ID = "cells-calib-001"

OUTPUT_FILE = Path("coords3.json")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """
    Универсальный запрос подтверждения.
    Возвращает True/False.
    """
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        ans = input(prompt + suffix).strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes", "д", "да"):
            return True
        if ans in ("n", "no", "н", "нет"):
            return False
        print("Пожалуйста, ответьте 'y' или 'n'.")


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
    print("=== Калибровка: FreeDrive → вводите имена точек; пустое имя — выход ===")

    # Если файл уже существует — подгружаем, чтобы дозаписывать
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

            # Проверим дубликаты
            if name in saved:
                if not ask_yes_no(f"Точка «{name}» уже существует. Перезаписать?", default=False):
                    print("   [-] Пропускаем сохранение с таким именем.")
                    continue

            input(f"Наведите TCP в целевую позицию для «{name}» и нажмите Enter, чтобы считать координаты…")

            try:
                pose = safe_get_pose(manip, timeout_seconds=5.0)
            except Exception as e:
                print(f"   [!] Ошибка чтения координат: {e}")
                if not ask_yes_no("Повторить попытку чтения координат?", default=True):
                    continue
                # одна повторная попытка
                try:
                    pose = safe_get_pose(manip, timeout_seconds=5.0)
                except Exception as e2:
                    print(f"   [!] Снова не удалось: {e2}. Пропускаем точку.")
                    continue

            print(f"   [→] {name}: {pose}")

            if ask_yes_no(f"Сохранить точку «{name}»?", default=True):
                saved[name] = pose
                # Сохраняем на диск сразу, чтобы ничего не потерять
                OUTPUT_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"   [✓] Сохранено. Всего точек: {len(saved)}")
            else:
                print("   [-] Не сохраняем.")

        # Итог
        OUTPUT_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[✓] Готово. Сохранено {len(saved)} точек в {OUTPUT_FILE.resolve()}")

    finally:
        try:
            manip.disconnect()
            print("[*] Отключено.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
