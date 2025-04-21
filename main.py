import os
from pathlib import Path
import shutil
import threading
import time
from src.constants import LOG_DIR, FRAMES_DIR
from src.cli import interactive_control
from src.restore_session import *

def setup_frames_dir():
    """Создает папку для кадров с .gitignore если не существует"""
    try:
        # Создаем папку (если не существует)
        os.makedirs(FRAMES_DIR, exist_ok=True)
        
        # Путь к .gitignore
        gitignore_path = Path(FRAMES_DIR) / ".gitignore"
        
        # Создаем .gitignore только если его нет
        if not gitignore_path.exists():
            with open(gitignore_path, 'w') as f:
                f.write(f"# Created by {__file__}\n*\n")
                
    except Exception as e:
        print(f"Ошибка при создании папки для кадров: {e}")

def main():
    """Основная функция для создания и запуска сети"""
    # Удаляем папку с логами, если она существует
    if os.path.exists(LOG_DIR):
        shutil.rmtree(LOG_DIR)
    
    # Создаем папку для логов
    os.makedirs(LOG_DIR)

    # Создаем папку для кадров
    setup_frames_dir()

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

    # Запуск симуляции пользователя вместо интерактивного управления
    if os.environ.get("USER_SIMULATION"):
        from src.user import simulate_user
        simulate_user(network, duration=30)  # 2 минуты симуляции
    else:
         # Запускаем интерактивное управление
        print("=== Модель самоорганизующейся P2P-сети ===")
        print("Доступные команды: info, scan, send, route, nodes, help")
        print("Для переключения между узлами используйте команду 'switch'")
        print("Для выхода введите 'exit' или 'q'")
        
        interactive_control(network)

if __name__ == "__main__":
    main()
