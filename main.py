import os
from pathlib import Path
import threading
import time
from src.constants import LOG_DIR, FRAMES_DIR, CONFIGS_DIR
from src.cli import interactive_control
from src.restore_session import *

def setup_dirs():
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

def main():
    """Основная функция для создания и запуска сети"""
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
    
    interactive_control(network)

if __name__ == "__main__":
    main()
