import random
import math
from typing import List
from src.models import Position
from src.network_simulator import NetworkSimulator
from src.p2p_node import P2PNode

def generate_random_network(
    num_nodes: int = 8,
    area_size: int = 10000,
    min_bitrate: int = 5000,
    max_bitrate: int = 20000,
    mobile_prob: float = 0.3
) -> NetworkSimulator:
    """
    Генерирует случайную P2P-сеть с заданными параметрами
    
    :param num_nodes: Количество узлов в сети
    :param area_size: Размер области (квадрат area_size x area_size)
    :param min_bitrate: Минимальная скорость передачи данных (бит/с)
    :param max_bitrate: Максимальная скорость передачи данных (бит/с)
    :param mobile_prob: Вероятность того, что узел будет мобильным (имеет скорость и направление)
    :return: Объект NetworkSimulator с созданной сетью
    """
    network = NetworkSimulator()
    
    for node_id in range(1, num_nodes + 1):
        # Случайные координаты
        x = random.randint(0, area_size)
        y = random.randint(0, area_size)
        position = Position(x, y)
        
        # Случайная скорость передачи данных
        bitrate = random.randint(min_bitrate, max_bitrate)
        
        # Параметры для мобильных узлов
        velocity = 0
        direction = 0
        if random.random() < mobile_prob:
            velocity = random.uniform(1, 10)  # Скорость от 1 до 10 единиц/сек
            direction = random.uniform(0, 2 * math.pi)  # Случайное направление
            
        # Создаем узел
        node = P2PNode(
            node_id=node_id,
            position=position,
            network=network,
            bitrate=bitrate,
            velocity=velocity,
            direction=direction
        )
        
        # Добавляем узел в сеть
        network.add_node(node)
        node.start()
    
    return network

def get_network_configuration1():
    network = NetworkSimulator()
    
    # Создаем несколько узлов
    node1 = P2PNode(1, Position(0, 0), network, bitrate=10000)
    node2 = P2PNode(2, Position(5000, 0), network, bitrate=8000)
    node3 = P2PNode(3, Position(0, 5000), network, bitrate=12000)
    node4 = P2PNode(4, Position(5000, 5000), network, velocity=5, direction=math.pi/4, bitrate=15000)

    nodes_list = [node1, node2, node3, node4]

    for node in nodes_list:
        network.add_node(node)
        node.start()

    return network
