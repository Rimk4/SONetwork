import json
import queue
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
from src.models import Frame
from src.constants import R, FRAMES_DIR
import matplotlib.pyplot as plt
import time
import os

class NetworkSimulator:
    """Класс для симуляции радиоканала и задержек передачи"""

    def __init__(self):
        self.nodes = {}
        self.frame_queue = queue.PriorityQueue()
        self.current_time = datetime.now()
        self.start_time = self.current_time

    def add_node(self, node: 'P2PNode'):
        self.nodes[node.node_id] = node

    def visualize(self, observer_id: int = None, frame_name: str = None):
        """Визуализация сети с узлами и их соединениями"""
        # Создаем папку для сохранения кадров
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        output_dir = f"{FRAMES_DIR}/network_frames_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        plt.figure(figsize=(10, 8))
        # Отображение всех узлов
        for node_id, node in self.nodes.items():
            position = node.state.position
            plt.plot(position.x, position.y, 'bo')
            plt.text(position.x, position.y, f'{node_id}', fontsize=8)

            # Показать зону покрытия для наблюдателя
            if observer_id and node_id == observer_id:
                circle = plt.Circle((position.x, position.y), R, 
                                color='r', fill=False)
                plt.gca().add_patch(circle)

        # Показать связи между узлами
        for i, node1 in enumerate(self.nodes.values()):
            pos1 = node1.state.position
            for node2 in list(self.nodes.values())[i+1:]:
                pos2 = node2.state.position
                distance = math.sqrt((pos1.x-pos2.x)**2 + (pos1.y-pos2.y)**2)
                if distance <= R:
                    plt.plot([pos1.x, pos2.x], [pos1.y, pos2.y], 'g-', alpha=0.3)

        plt.title(f"Сеть из {len(self.nodes)} мобильных узлов\n(Зона покрытия наблюдателя {'N/A' if not observer_id else observer_id} показана красным)")
        plt.xlabel("Координата X (м)")
        plt.ylabel("Координата Y (м)")
        plt.grid(True)
        # Сохраняем кадр
        if frame_name is None:
            frame_name = f"network_plot_{int(time.time())}.png"
            frame_path = os.path.join(output_dir, frame_name)
        else:
            frame_path = frame_name
        plt.savefig(frame_path)
        plt.close()

    def transmit_frame(self, frame: Frame, sender_id: int, receiver_id: int) -> bool:
        """Отправка фрейма с учётом задержек и вероятности потери"""
        if sender_id not in self.nodes or receiver_id not in self.nodes:
            return False

        sender = self.nodes[sender_id]
        receiver = self.nodes[receiver_id]

        # Проверка расстояния
        distance = sender.state.position.distance_to(receiver.state.position)
        if distance > R:
            sender.logger.debug(f"Узел {receiver_id} вне зоны покрытия узла {sender_id} (расстояние {distance:.1f} м)")
            # print(f"NetworkSimulator: Узел {receiver_id} вне зоны покрытия узла {sender_id} (расстояние {distance:.1f} м)")
            return False

        # Вероятность успешной передачи (из отчёта)
        alpha = 0.3
        p_success = math.exp(-alpha * distance / R)
        if random.random() > p_success:
            sender.logger.debug(f"Фрейм потерян из-за ошибки передачи (вероятность {p_success:.2f})")
            return False

        # Расчет времени передачи (из отчёта)
        frame_size = 4 + len(frame.payload) + 2 + 8  # заголовок + данные + CRC + временная метка
        L = frame_size * 8  # размер в битах
        B = sender.bitrate  # битрейт
        transmission_time = L / B  # время передачи в секундах

        # Задержка распространения сигнала
        propagation_delay = distance / 3e8

        # Общее время доставки
        total_delay = transmission_time + propagation_delay

        """
            Transmission time доминирует при:
                - Больших размерах данных (например, файлы)
                - Низком битрейте (например, модемные соединения)
            Propagation delay становится значимым при:
                - Очень больших расстояниях (спутниковая связь)
                - Маленьких фреймах (например, ping-запросы)
        """

        # Запланировать доставку фрейма
        delivery_time = self.current_time + timedelta(seconds=total_delay)
        self.frame_queue.put((delivery_time, frame, receiver_id))

        sender.logger.debug(f"Фрейм от {sender_id} к {receiver_id} будет доставлен через {total_delay:.4f} сек")
        return True

    def process_events(self):
        """Обработка всех запланированных событий"""
        # Обновляем текущее время симуляции
        self.current_time = datetime.now()

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

                # Логируем факт доставки (уровень DEBUG)
                self.nodes[receiver_id].logger.debug(
                    f"Фрейм {frame.type} доставлен узлу {receiver_id}"
                )

    def remove_node(self, node_id: int) -> Optional[bool]:
        """
        Удаление узла из сети.
        
        Args:
            node_id: ID узла для удаления
            
        Returns:
            bool: True если узел был удален, False если не найден
            None: если произошла ошибка
        """
        if node_id not in self.nodes:
            print(f"NetworkSimulator: Попытка удалить несуществующий узел {node_id}")
            return False
            
        try:
            # Удаляем все фреймы, связанные с этим узлом
            new_queue = queue.PriorityQueue()
            removed_frames = 0
            
            while not self.frame_queue.empty():
                try:
                    delivery_time, frame, receiver_id = self.frame_queue.get_nowait()
                    if receiver_id != node_id and frame.sender_id != node_id:
                        new_queue.put((delivery_time, frame, receiver_id))
                    else:
                        removed_frames += 1
                except queue.Empty:
                    break
                    
            self.frame_queue = new_queue
            del self.nodes[node_id]
            
            print(
                f"NetworkSimulator: Узел {node_id} удален. "
                f"Удалено фреймов: {removed_frames}. "
                f"Осталось узлов: {len(self.nodes)}"
            )
            return True
            
        except Exception as e:
            print(f"NetworkSimulator: Ошибка при удалении узла {node_id}: {str(e)}")
            return None

    def save_network_config(self, filename: str = None) -> str:
        """
        Сохраняет текущую конфигурацию сети в JSON файл.
        
        Args:
            filename: Имя файла для сохранения. Если None, генерируется автоматически.
            
        Returns:
            str: Путь к сохраненному файлу
        """
        # Создаем папку out, если ее нет
        output_dir = Path("out")
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
                "node_count": len(self.nodes),
                "simulation_start_time": self.start_time.isoformat(),
                "current_sim_time": self.current_time.isoformat()
            },
            "nodes": {
                node_id: {
                    "position": {
                        "x": node.state.position.x,
                        "y": node.state.position.y
                    },
                    "bitrate": node.bitrate,
                    "state": {  # Сохраняем состояние как словарь
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
                    "frame_type": frame.type,
                    "frame_sender": frame.sender_id
                }
                for delivery_time, frame, receiver_id in self.frame_queue.queue
            ]
        }
        
        # Сохраняем в файл
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        return str(filepath)

    @classmethod
    def load_network_config(cls, filepath: str) -> Optional['NetworkSimulator']:
        """
        Загружает конфигурацию сети из JSON файла и создает новый экземпляр NetworkSimulator.
        
        Args:
            filepath: Путь к JSON файлу с конфигурацией
            
        Returns:
            NetworkSimulator: Восстановленный экземпляр симулятора
            None: Если произошла ошибка загрузки
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Создаем новый экземпляр симулятора
            simulator = cls()
            
            # Восстанавливаем временные метки
            simulator.start_time = datetime.fromisoformat(config['metadata']['simulation_start_time'])
            simulator.current_time = datetime.fromisoformat(config['metadata']['current_sim_time'])
            
            # Восстанавливаем узлы (только базовые параметры, реальные узлы нужно добавить через add_node)
            # Здесь предполагается, что узлы будут добавлены позже через add_node
            simulator.nodes = {}  # Очищаем, так как реальные узлы будут добавляться отдельно
            
            # Восстанавливаем очередь фреймов
            simulator.frame_queue = queue.PriorityQueue()
            for frame_data in config['pending_frames']:
                delivery_time = datetime.fromisoformat(frame_data['delivery_time'])
                frame = Frame(
                    type=frame_data['frame_type'],
                    sender_id=frame_data['frame_sender'],
                    payload=b''  # В реальной реализации нужно восстановить payload
                )
                simulator.frame_queue.put((delivery_time, frame, frame_data['receiver_id']))
            
            return simulator
            
        except Exception as e:
            print(f"Ошибка загрузки конфигурации сети: {str(e)}")
            return None

    def restore_nodes_from_config(self, config_file: str, node_creator: callable) -> bool:
        """
        Восстанавливает узлы сети из конфигурационного файла.
        
        Args:
            config_file: Путь к JSON файлу с конфигурацией
            node_creator: Функция для создания узлов (должна принимать node_id и config)
            
        Returns:
            bool: True если восстановление прошло успешно, False если произошла ошибка
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for node_id, node_config in config['nodes'].items():
                node = node_creator(int(node_id), node_config)
                self.add_node(node)
            
            return True
            
        except Exception as e:
            print(f"Ошибка восстановления узлов: {str(e)}")
            return False
