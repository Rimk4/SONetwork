import os
from pathlib import Path
import shutil
import argparse
import threading
import time
from src.constants import LOG_DIR, FRAMES_DIR, CONFIGS_DIR
from src.cli import interactive_control
from src.restore_session import *

def setup_dirs() -> None:
    """Создает папки с .gitignore если не существует"""
    directories = [LOG_DIR, FRAMES_DIR, CONFIGS_DIR]
    for dir in directories:
        try:
            # Создаем папку (если не существует)
            os.makedirs(dir, exist_ok=True)
            
            # Путь к .gitignore
            gitignore_path = Path(dir) / ".gitignore"
            
            # Создаем .gitignore только если его нет
            if not gitignore_path.exists():
                with open(gitignore_path, 'w') as f:
                    f.write(f"# Created by {__file__}\n*\n")
                    
        except Exception as e:
            print(f"Ошибка при создании папки {dir}: {e}")

def parse_args():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(description="Модель самоорганизующейся P2P-сети")
    parser.add_argument(
        "-l", "--load",
        type=str,
        help="Путь к файлу конфигурации для загрузки сети",
        default=None
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Запустить приложение с графическим интерфейсом"
    )
    return parser.parse_args()

def startNetwork() -> NetworkSimulator:
    """Основная функция для создания и запуска сети"""
    # Удаляем папку с логами
    if os.path.exists(LOG_DIR):
        shutil.rmtree(LOG_DIR)
    
    # Удаляем папку с фреймами
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)

    # Подготовка директорий
    setup_dirs()

    args = parse_args()

    # Инициализация сети
    network = initialize_network(args.load)

    # Запускаем обработчик событий сети в отдельном потоке
    def network_processor():
        while True:
            network.process_events()
            time.sleep(0.1)
    
    net_thread = threading.Thread(target=network_processor, daemon=True)
    net_thread.start()

    # Запускаем интерактивное управление
    print("=== Модель самоорганизующейся P2P-сети ===")
    print("Доступные команды: info, scan, send, route, nodes, help")
    print("Для переключения между узлами используйте команду 'switch'")
    print("Для выхода введите 'exit' или 'q'")

    return network    

if __name__ == "__main__":
    network = startNetwork()
    if parse_args().gui:
        from gui import start_gui
        start_gui(network)
    else:
        # Существующая CLI-логика
        interactive_control(network)
