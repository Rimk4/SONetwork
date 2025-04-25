import json
import queue
import random
import math
from datetime import timedelta
from typing import Dict, Optional, Any
from pathlib import Path
from src.SimulatorDateTime import SimulatorDateTime as datetime
from src.models import Frame, Position
from src.constants import CONFIGS_DIR, R, FRAMES_DIR, LOG_DIR
import matplotlib.pyplot as plt
import time
import logging
import os

class NetworkSimulator:
    """Класс для симуляции сети радиоканалов"""

    def __init__(self) -> None:
        self.nodes: Dict[int, 'P2PNode'] = {}
        self.frame_queue = queue.PriorityQueue()
        self.current_time = datetime.now()
        self.start_time = self.current_time
        self._setup_logger()
        self.transmission_stats = {
            "success": 0,
            "failed_distance": 0,
            "failed_transmission": 0,
            "total": 0
        }

    def _setup_logger(self) -> None:
        """Настройка логгера для симулятора"""
        self.logger = logging.getLogger('NetworkSimulator')
        self.logger.setLevel(logging.INFO)
        
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, 'network_simulator.log')
        
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def add_node(self, node: 'P2PNode') -> None:
        """Добавление узла в сеть с проверкой уникальности ID"""
        if node.node_id in self.nodes:
            raise ValueError(f"Узел с ID {node.node_id} уже существует")
        self.nodes[node.node_id] = node
        self.logger.info(f"Добавлен узел {node.node_id} на позиции ({node.state.position.x:.1f}, {node.state.position.y:.1f})")

    def visualize(self, observer_id: Optional[int] = None, frame_name: Optional[str] = None) -> str:
        """Визуализация сети с узлами, их соединениями и выделением зоны покрытия"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"{FRAMES_DIR}/network_frames_{timestamp}")
        output_dir.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(12, 10))
        
        # Отображение узлов и их соединений
        for node_id, node in self.nodes.items():
            position = node.state.position
            color = 'red' if node_id == observer_id else 'blue'
            plt.plot(position.x, position.y, 'o', color=color, markersize=10)
            plt.text(position.x, position.y, f'{node_id}', fontsize=12, ha='center', va='center')
            
            # Зона покрытия для наблюдателя
            if node_id == observer_id:
                circle = plt.Circle((position.x, position.y), R, color='r', fill=False, linestyle='--')
                plt.gca().add_patch(circle)
        
        # Соединения между узлами
        connected = set()
        for node1 in self.nodes.values():
            for node2 in self.nodes.values():
                if node1.node_id != node2.node_id and (node2.node_id, node1.node_id) not in connected:
                    distance = node1.state.position.distance_to(node2.state.position)
                    if distance <= R:
                        plt.plot(
                            [node1.state.position.x, node2.state.position.x],
                            [node1.state.position.y, node2.state.position.y],
                            'g-', alpha=0.3, linewidth=0.5
                        )
                        connected.add((node1.node_id, node2.node_id))

        title = f"Сеть из {len(self.nodes)} узлов (время симуляции: {(self.current_time - self.start_time).total_seconds():.1f} сек)"
        if observer_id is not None:
            title += f"\nЗона покрытия узла {observer_id} показана красным"
        
        plt.title(title)
        plt.xlabel("Координата X (м)")
        plt.ylabel("Координата Y (м)")
        plt.grid(True, alpha=0.3)
        
        # Сохранение изображения
        if frame_name is None:
            frame_name = f"network_{int(time.time())}.png"
            frame_path = os.path.join(output_dir, frame_name)
        else:
            frame_path = frame_name
        plt.savefig(frame_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return frame_path

    def transmit_frame(self, frame: Frame, sender_id: int, receiver_id: int) -> bool:
        """Отправка фрейма с учетом физических ограничений канала"""
        self.transmission_stats['total'] += 1
        
        # Проверка существования узлов
        if sender_id not in self.nodes or receiver_id not in self.nodes:
            self.logger.warning(f"Попытка передачи между несуществующими узлами: {sender_id}->{receiver_id}")
            return False

        sender = self.nodes[sender_id]
        receiver = self.nodes[receiver_id]

        # Проверка расстояния
        distance = sender.state.position.distance_to(receiver.state.position)
        if distance > R:
            self.logger.debug(f"Узел {receiver_id} вне зоны покрытия (расстояние {distance:.1f} м > {R} м)")
            self.transmission_stats["failed_distance"] += 1
            return False

        # Модель потерь в канале
        success_prob = self._calculate_transmission_probability(distance, sender.bitrate, frame)
        if random.random() > success_prob:
            self.transmission_stats["failed_transmission"] += 1
            sender.logger.debug(f"Фрейм потерян из-за ошибки передачи (вероятность успеха {success_prob:.2f})")
            return False

        # Расчет времени доставки
        delay = self._calculate_transmission_delay(distance, sender.bitrate, frame)
        delivery_time = self.current_time + timedelta(seconds=delay)

        # Планирование доставки
        self.frame_queue.put((delivery_time, frame, receiver_id))
        self.transmission_stats["success"] += 1
        
        sender.logger.info(f"Фрейм {frame.type} к {receiver_id} запланирован на {delivery_time.strftime('%H:%M:%S.%f')}")
        return True

    def _calculate_transmission_probability(self, distance: float, bitrate: int, frame: Frame) -> float:
        """Расчет вероятности успешной передачи"""
        # Базовая вероятность с учетом расстояния
        alpha = 0.3
        distance_factor = math.exp(-alpha * distance / R)
        
        # Влияние размера фрейма (большие фреймы более подвержены ошибкам)
        size_factor = 1.0 - (len(frame.payload) / 1024) * 0.1  # Коэффициент для фреймов до 1KB
        
        # Влияние битрейта (высокие скорости более подвержены ошибкам)
        bitrate_factor = 1.0 - (bitrate / 10000) * 0.05  # Коэффициент для битрейта до 10kbps
        
        return distance_factor * size_factor * bitrate_factor

    def _calculate_transmission_delay(self, distance: float, bitrate: int, frame: Frame) -> float:
        """Расчет времени доставки фрейма"""
        # Время передачи (биты / битрейт)
        frame_size_bits = (4 + len(frame.payload) + 2 + 8) * 8  # заголовок + данные + CRC + метка времени
        transmission_time = frame_size_bits / bitrate
        
        # Задержка распространения сигнала
        propagation_delay = distance / 3e8
        
        # Случайные факторы (помехи, очередь и т.д.)
        random_factor = random.uniform(0.9, 1.1)
        
        return (transmission_time + propagation_delay) * random_factor

    def process_events(self) -> None:
        """Обработка всех запланированных событий"""
        # Обновляем текущее время симуляции
        self.current_time = datetime.now()
        processed = 0

        # Обрабатываем все фреймы в очереди, пока она не пуста
        while not self.frame_queue.empty():
            # Просматриваем первый элемент очереди (без извлечения)
            delivery_time, frame, receiver_id = self.frame_queue.queue[0]

            # Если время доставки еще не наступило, прерываем цикл
            if delivery_time > self.current_time:
                break
            
            # Извлекаем фрейм из очереди (теперь он будет обработан)
            self.frame_queue.get()
            
            # Проверяем, существует ли еще узел-получатель
            if receiver_id in self.nodes:
                # Передаем фрейм целевому узлу
                self.nodes[receiver_id].receive_frame(frame)
                processed += 1

                # Логируем факт доставки (уровень DEBUG)
                self.logger.debug(
                    f"Фрейм {frame.type} доставлен узлу {receiver_id}"
                )
        
        if processed > 0:
            self.logger.debug(f"Обработано {processed} фреймов")

    def remove_node(self, node_id: int) -> bool:
        """Удаление узла с очисткой связанных фреймов"""
        if node_id not in self.nodes:
            self.logger.warning(f"Попытка удалить несуществующий узел {node_id}")
            return False
            
        try:
            # Фильтрация очереди фреймов
            new_queue = queue.PriorityQueue()
            removed_frames = 0
            
            while not self.frame_queue.empty():
                delivery_time, frame, receiver_id = self.frame_queue.get_nowait()
                if receiver_id != node_id and frame.sender_id != node_id:
                    new_queue.put((delivery_time, frame, receiver_id))
                else:
                    removed_frames += 1
            
            self.frame_queue = new_queue
            del self.nodes[node_id]
            
            self.logger.info(
                f"Узел {node_id} удален. Удалено фреймов: {removed_frames}. "
                f"Осталось узлов: {len(self.nodes)}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления узла {node_id}: {str(e)}")
            return False

    def kill_node(self, node_id: int) -> None:
        if len(self.nodes) <= 1:
            print("Нельзя удалить последний узел в сети!")
            return
        
        print(f"Удаляем узел {node_id}...")
        node = self.nodes[node_id]
        node.stop()
        node.join()
        self.remove_node(node_id)
        
        # Переключаемся на другой доступный узел
        self.current_node_id = next(iter(self.nodes))
        print(f"Переключено на узел {self.current_node_id}")
    
    def move_node(self, node_id: int, position: Position):
        if node_id not in self.nodes:
            self.logger.info("Узел с таким ID не найден")
            return
            
        node = self.nodes[node_id]
        node.state.position = position
        self.logger.info(f"Узел {node_id} перемещен в ({position.x:.1f}, {position.y:.1f})")
        print(f"Узел {node_id} перемещен в ({position.x:.1f}, {position.y:.1f})")

    def get_network_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы сети"""
        return {
            'nodes_count': len(self.nodes),
            'pending_frames': self.frame_queue.qsize(),
            'transmission_stats': self.transmission_stats,
            'uptime': str(self.current_time - self.start_time),
            'current_time': self.current_time.isoformat()
        }

    def save_network_config(self, filename: Optional[str] = None) -> str:
        """Сохранение конфигурации сети в JSON файл"""
        output_dir = Path(CONFIGS_DIR)
        output_dir.mkdir(exist_ok=True)
        
        # Формируем имя файла
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_config_{timestamp}.json"
        elif not filename.endswith(".json"):
            filename += ".json"
            
        filepath = output_dir / filename
        
        # Формируем данные для сохранения
        config = {
            "metadata": {
                "save_time": datetime.now().isoformat(),
                "stats": self.get_network_stats()
            },
            "nodes": {
                node_id: {
                    "position": {
                        "x": node.state.position.x,
                        "y": node.state.position.y
                    },
                    "bitrate": node.bitrate,
                    "state": {
                        "velocity": node.state.velocity,
                        "direction": node.state.direction,
                        "last_update": node.state.last_update.isoformat()
                    }
                }
                for node_id, node in self.nodes.items()
            },
            "pending_frames": [
                {
                    "delivery_time": delivery_time.isoformat(),
                    "receiver_id": receiver_id,
                    "frame": {
                        "type": frame.type,
                        "sender_id": frame.sender_id,
                        "destination_id": frame.destination_id,
                        "size": len(frame.payload)
                    }
                }
                for delivery_time, frame, receiver_id in self.frame_queue.queue
            ]
        }
        
        # Сохраняем в файл
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        self.logger.info(f"Конфигурация сохранена в {filepath}")
        return str(filepath)

    @classmethod
    def load_network_config(cls, filepath: str) -> Optional['NetworkSimulator']:
        """Загрузка конфигурации сети из файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Создаем новый экземпляр симулятора
            simulator = cls()
            simulator.start_time = datetime.fromisoformat(config['metadata']['save_time'])
            simulator.current_time = datetime.fromisoformat(config['metadata']['stats']['current_time'])
            datetime.set_start_time(simulator.start_time)

            # Восстановление статистики
            simulator.transmission_stats = config['metadata']['stats']['transmission_stats']
            
            # Восстановление очереди фреймов
            simulator.frame_queue = queue.PriorityQueue()
            for frame_data in config['pending_frames']:
                delivery_time = datetime.fromisoformat(frame_data['delivery_time'])
                frame = Frame(
                    type=frame_data['frame']['type'],
                    sender_id=frame_data['frame']['sender_id'],
                    destination_id=frame_data['frame'].get('destination_id'),
                    payload=b''  # Восстановление payload не реализовано
                )
                simulator.frame_queue.put((delivery_time, frame, frame_data['receiver_id']))
            
            return simulator
            
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигурации сети: {str(e)}")
            return None

    def restore_nodes_from_config(self, config_file: str, node_creator: callable) -> bool:
        """Восстановление узлов из конфигурационного файла"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for node_id, node_config in config['nodes'].items():
                node = node_creator(int(node_id), node_config)
                self.add_node(node)
            
            self.logger.info(f"Восстановлено {len(config['nodes'])} узлов из конфигурации")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка восстановления узлов: {str(e)}")
            return False
