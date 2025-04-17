import os
import shutil
import threading
import time
from src.constants import LOG_DIR
from src.network_generator import *
from src.cli import interactive_control

def main():
    # Удаляем папку с логами, если она существует
    if os.path.exists(LOG_DIR):
        shutil.rmtree(LOG_DIR)
    
    # Создаем папку для логов
    os.makedirs(LOG_DIR)

    """Основная функция для создания и запуска сети"""
    network = generate_random_network()

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
    
    # Запускаем обработчик событий сети в отдельном потоке
    def network_processor():
        while True:
            network.process_events()
            time.sleep(0.1)
    
    net_thread = threading.Thread(target=network_processor, daemon=True)
    net_thread.start()

if __name__ == "__main__":
    main()
