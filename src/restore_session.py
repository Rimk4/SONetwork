from src.network_generator import *
from typing import Optional
import argparse
from datetime import datetime

def parse_args():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(description="Модель самоорганизующейся P2P-сети")
    parser.add_argument(
        "-l", "--load",
        type=str,
        help="Путь к файлу конфигурации для загрузки сети",
        default=None
    )
    return parser.parse_args()

def restore_network(config_file: str) -> Optional[NetworkSimulator]:
    """Полное восстановление сети из конфигурационного файла"""
    # 1. Загружаем базовую конфигурацию
    network = NetworkSimulator.load_network_config(config_file)
    if not network:
        return None
    
    # 2. Восстанавливаем узлы
    def node_creator(node_id, config):
        node = P2PNode(
            node_id=node_id,
            position=Position(config["position"]["x"], config["position"]["y"]),
            network=network,
            velocity=config["state"]["velocity"],
            direction=config["state"]["direction"],
            bitrate=config["bitrate"]
        )
        node.state.last_update = datetime.fromisoformat(config["state"]["last_update"])
        node.start()

        return node

    if not network.restore_nodes_from_config(config_file, node_creator):
        return None

    return network

def initialize_network(config_path=None):
    """
    Инициализирует сеть - либо загружает из конфига, либо создаёт новую
    Args:
        config_path: Путь к файлу конфигурации (None для новой сети)
    Returns:
        NetworkSimulator: инициализированный экземпляр сети
    """
    if config_path:
        print(f"Загружаем сеть из файла: {config_path}")
        try:
            return restore_network(config_path)
        except Exception as e:
            print(f"Ошибка загрузки сети: {e}")
    
    print("Создаём новую случайную сеть")
    return generate_random_network()
