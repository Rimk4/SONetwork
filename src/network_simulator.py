import logging
import queue
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Optional
from src.models import Frame
from src.constants import R

class NetworkSimulator:
    """Класс для симуляции радиоканала и задержек передачи"""
    
    def __init__(self, simulation_time=None):
        self.nodes = {}
        self.frame_queue = queue.PriorityQueue()
        self.current_time = datetime.now()
        self.simulation_time = simulation_time  # в секундах
        self.start_time = datetime.now()
        self._should_stop = False  # Флаг для мягкого завершения
    
    def add_node(self, node: 'P2PNode'):
        self.nodes[node.node_id] = node
    
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
            print(f"NetworkSimulator: Узел {receiver_id} вне зоны покрытия узла {sender_id} (расстояние {distance:.1f} м)")
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
    
    def stop_simulation(self):
        """Мягкое завершение симуляции"""
        self._should_stop = True
        for node in self.nodes.values():
            node.stop()
            node.join()

    def process_events(self):
        """Обработка всех запланированных событий"""
        # Обновляем текущее время симуляции
        self.current_time = datetime.now()

        if self._should_stop:
            return False  # Сигнализируем о необходимости остановки
        
        if self.simulation_time is not None:
            if self.current_time - self.start_time >= timedelta(seconds=self.simulation_time):
                print(f"Симуляция завершена по истечении {self.simulation_time} секунд")
                self.stop_simulation()
                return False

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

        return True

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
