import queue
import random
import math
from datetime import datetime, timedelta
from typing import Dict
from src.models import Frame
from src.constants import R

class NetworkSimulator:
    """Класс для симуляции радиоканала и задержек передачи"""
    
    def __init__(self):
        self.nodes = {}
        self.frame_queue = queue.PriorityQueue()
        self.current_time = datetime.now()
    
    def add_node(self, node: 'P2PNode'):
        self.nodes[node.node_id] = node
    
    def transmit_frame(self, frame: Frame, sender_id: int, receiver_id: int):
        """Отправка фрейма с учётом задержек и вероятности потери"""
        if sender_id not in self.nodes or receiver_id not in self.nodes:
            return False
        
        sender = self.nodes[sender_id]
        receiver = self.nodes[receiver_id]
        
        # Проверка расстояния
        distance = sender.state.position.distance_to(receiver.state.position)
        if distance > R:
            sender.logger.debug(f"Узел {receiver_id} вне зоны покрытия узла {sender_id} (расстояние {distance:.1f} м)")
            print(f"Узел {receiver_id} вне зоны покрытия узла {sender_id} (расстояние {distance:.1f} м)")
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
        
        # Запланировать доставку фрейма
        delivery_time = self.current_time + timedelta(seconds=total_delay)
        self.frame_queue.put((delivery_time, frame, receiver_id))
        
        sender.logger.debug(f"Фрейм от {sender_id} к {receiver_id} будет доставлен через {total_delay:.4f} сек")
        return True
    
    def process_events(self):
        """Обработка всех запланированных событий"""
        self.current_time = datetime.now()
        while not self.frame_queue.empty():
            delivery_time, frame, receiver_id = self.frame_queue.queue[0]
            if delivery_time > self.current_time:
                break
            
            self.frame_queue.get()
            if receiver_id in self.nodes:
                self.nodes[receiver_id].receive_frame(frame)
                self.nodes[receiver_id].logger.debug(f"Фрейм {frame.type} доставлен узлу {receiver_id}")

    def remove_node(self, node_id: int):
        """Удаление узла из сети"""
        if node_id in self.nodes:
            # Удаляем все запланированные фреймы для этого узла
            new_queue = queue.PriorityQueue()
            while not self.frame_queue.empty():
                delivery_time, frame, receiver_id = self.frame_queue.get()
                if receiver_id != node_id and frame.sender_id != node_id:
                    new_queue.put((delivery_time, frame, receiver_id))
            self.frame_queue = new_queue
            del self.nodes[node_id]
            print(f"Узел {node_id} полностью удален из сети")
