import os
import shutil
import threading
import time
import math
from src.constants import LOG_DIR, TMP_DIR
from src.models import Position
from src.network_simulator import NetworkSimulator
from src.p2p_node import P2PNode
from src.cli import interactive_control

def main():
    # Удаляем папку с логами, если она существует
    if os.path.exists(LOG_DIR):
        shutil.rmtree(LOG_DIR)
    
    # Создаем папку для логов
    os.makedirs(LOG_DIR)

    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)

    """Основная функция для создания и запуска сети"""
    network = NetworkSimulator()
    
    # Создаем несколько узлов
    node1 = P2PNode(1, Position(0, 0), network, bitrate=10000)
    node2 = P2PNode(2, Position(5000, 0), network, bitrate=8000)
    node3 = P2PNode(3, Position(0, 5000), network, bitrate=12000)
    node4 = P2PNode(4, Position(5000, 5000), network, velocity=5, direction=math.pi/4, bitrate=15000)

    nodes_list = [node1, node2, node3, node4]
    
    # Добавляем узлы в сеть и запускаем их
    for node in nodes_list:
        network.add_node(node)
        node.start()
    
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
