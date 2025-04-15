import os
import logging
import random
import queue
import threading
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Tuple
from src.models import Position, Frame, NodeState, RoutingEntry
from src.constants import T_SCAN, T_TIMEOUT, T_SLEEP_MIN, T_SLEEP_MAX, LOG_DIR, R

class P2PNode(threading.Thread):
    """Класс, реализующий узел P2P-сети"""
    
    def __init__(self, node_id: int, position: Position, network: 'NetworkSimulator', 
                 velocity: float = 0.0, direction: float = 0.0, bitrate: int = 5000):
        super().__init__(daemon=True)
        self.node_id = node_id
        self.state = NodeState(position, velocity, direction)
        self.network = network
        self.bitrate = bitrate
        self.routing_table: Dict[int, RoutingEntry] = {}
        self.local_map: Dict[int, Tuple[Position, datetime]] = {}  # ID -> (position, last_update)
        self.message_queue = queue.Queue()
        self.running = True
        self.commands = {
            "info": self.cmd_info,
            "scan": self.cmd_scan,
            "send": self.cmd_send,
            "route": self.cmd_show_routes,
            "nodes": self.cmd_show_nodes,
            "help": self.cmd_help,
            "log": self.cmd_set_loglvl,
        }

        # Настройка логгера для узла
        self.logger = logging.getLogger(f"Node-{self.node_id}")
        self.logger.setLevel(logging.DEBUG)
        log_file_path = os.path.join(LOG_DIR, f"node_{self.node_id}.log")
        fh = logging.FileHandler(log_file_path)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Добавляем себя в локальную карту
        self.local_map[self.node_id] = (self.state.position, self.state.last_update)
        
        # Параметры из отчёта
        self.scan_interval = T_SCAN
        self.sleep_time = random.uniform(T_SLEEP_MIN, T_SLEEP_MAX)
        self.retry_timeout = 2  # базовый таймаут для повторных передач
        self.max_retries = 3  # максимальное число попыток
        
        print(f"P2PNode: Создан узел {self.node_id} на позиции ({position.x:.1f}, {position.y:.1f})")

    def run(self):
        """Основной цикл работы узла"""
        last_scan = datetime.now()
        
        while self.running:
            current_time = datetime.now()
            
            # Remove expired entries from local_map
            nodes_to_remove = []
            for node_id, (position, last_update) in self.local_map.items():
                if (current_time - last_update).total_seconds() > T_TIMEOUT:
                    nodes_to_remove.append(node_id)
            for node_id in nodes_to_remove:
                del self.local_map[node_id]
                self.logger.debug(f"Узел {node_id} удален из local_map")

            # Remove expired entries from routing_table
            routes_to_remove = []
            for node_id, entry in self.routing_table.items():
                if entry.expire_time <= current_time:
                    routes_to_remove.append(node_id)
            for node_id in routes_to_remove:
                del self.routing_table[node_id]
                self.logger.debug(f"Маршрут к узлу {node_id} удален из routing_table")

            # Обновление позиции
            delta_t = (current_time - self.state.last_update).total_seconds()
            if delta_t > 0:
                self.state.move(delta_t)
                self.local_map[self.node_id] = (self.state.position, current_time)
            
            # Периодическое сканирование соседей
            if (current_time - last_scan).total_seconds() >= self.scan_interval:
                self.scan_neighbors()
                last_scan = current_time
            
            # Обработка команд управления
            try:
                cmd = self.message_queue.get_nowait()
                self.process_command(cmd)
            except queue.Empty:
                pass
            
            # Короткая пауза для экономии CPU
            time.sleep(0.1)
    
    def process_command(self, cmd: str):
        """Обработка команд управления"""
        parts = cmd.split()
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command in self.commands:
            try:
                self.commands[command](*args)
            except Exception as e:
                print(f"P2PNode: Ошибка выполнения команды: {e}")
        else:
            print(f"P2PNode: Неизвестная команда: {command}. Введите 'help' для списка команд.")
    
    def cmd_info(self):
        """Вывод информации о текущем узле"""
        print(f"\n=== Информация об узле {self.node_id} ===")
        print(f"Позиция: ({self.state.position.x:.1f}, {self.state.position.y:.1f})")
        print(f"Скорость: {self.state.velocity:.1f} м/с, направление: {math.degrees(self.state.direction):.1f}°")
        print(f"Битрейт: {self.bitrate} бит/с")
        print(f"Размер локальной карты: {len(self.local_map)} узлов")
        print(f"Размер таблицы маршрутизации: {len(self.routing_table)} записей")
    
    def cmd_scan(self):
        """Инициировать сканирование соседей"""
        print(f"\nP2PNode: Узел {self.node_id} сканирование соседей...")
        self.scan_neighbors()
    
    def cmd_send(self, target_id: str, *message_parts: str) -> None:
        """Отправить сообщение другому узлу"""
        try:
            target_node_id = int(target_id)
            message = " ".join(message_parts)
            
            if target_node_id == self.node_id:
                print("P2PNode: Нельзя отправить сообщение самому себе!")
                return
            
            if target_node_id not in self.routing_table:
                print(f"P2PNode: Узел {target_node_id} не найден в таблице маршрутизации!")
                return
            
            # Создаем фрейм с сообщением
            frame = Frame("DATA", self.node_id, message.encode())
            next_hop = self.routing_table[target_node_id].next_hop
            
            if self.network.transmit_frame(frame, self.node_id, next_hop):
                print(f"P2PNode: Сообщение отправлено узлу {target_node_id} через {next_hop}")
            else:
                print("Ошибка передачи сообщения!")
        except ValueError:
            print("Неверный ID узла!")
    
    def cmd_show_routes(self):
        """Показать таблицу маршрутизации"""
        print("\n=== Таблица маршрутизации ===")
        if not self.routing_table:
            print("Таблица маршрутизации пуста")
            return

        print(f"{'ID узла':<10}{'След. прыжок':<15}{'Метрика':<10}{'Истекает':<20}")
        for node_id, entry in self.routing_table.items():
            expires_in = (entry.expire_time - datetime.now()).total_seconds()
            print(f"{node_id:<10}{entry.next_hop:<15}{entry.metric:<10.2f}{expires_in:.1f} сек")
    
    def cmd_show_nodes(self):
        """Показать известные узлы в локальной карте"""
        print("\n=== Локальная карта сети ===")
        if not self.local_map:
            print("Локальная карта пуста")
            return

        print(f"{'ID узла':<10}{'Позиция (x,y)':<25}{'Обновлено':<20}")
        for node_id, (pos, last_update) in self.local_map.items():
            age = (datetime.now() - last_update).total_seconds()
            coords = f'({pos.x:.1f}, {pos.y:.1f})'
            print(f"{node_id:<10}{coords:<25}{age:.1f} сек назад")

    def cmd_help(self):
        """Показать справку по командам"""
        print("\n=== Доступные команды ===")
        print("info - показать информацию об узле")
        print("scan - инициировать сканирование соседей")
        print("send <id> <message> - отправить сообщение узлу")
        print("route - показать таблицу маршрутизации")
        print("nodes - показать известные узлы")
        print("log <level> - set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
        print("help - показать эту справку")

    def cmd_set_loglvl(self, level: str):
        """Set the logging level for the node"""
        level = level.upper()
        if level == "DEBUG":
            self.logger.setLevel(logging.DEBUG)
            print("Уровень логгирования изменен на DEBUG")
        elif level == "INFO":
            self.logger.setLevel(logging.INFO)
            print("Уровень логгирования изменен на INFO")
        elif level == "WARNING":
            self.logger.setLevel(logging.WARNING)
            print("Уровень логгирования изменен на WARNING")
        elif level == "ERROR":
            self.logger.setLevel(logging.ERROR)
            print("Уровень логгирования изменен на ERROR")
        elif level == "CRITICAL":
            self.logger.setLevel(logging.CRITICAL)
            print("Уровень логгирования изменен на CRITICAL")
        else:
            print("Неверный уровень логгирования. Допустимые значения: DEBUG, INFO, WARNING, ERROR, CRITICAL")

    def scan_neighbors(self):
        """Процедура сканирования соседей (BEACON)"""
        beacon = Frame("BEACON", self.node_id, self.serialize_position())
        for node_id in self.network.nodes:
            if node_id != self.node_id:
                self.network.transmit_frame(beacon, self.node_id, node_id)
    
    def receive_frame(self, frame: Frame):
        """Обработка входящего фрейма"""
        self.logger.info(f"Узел {self.node_id} получил фрейм {frame.type} от {frame.sender_id}")
        
        if frame.type == "BEACON":
            self.process_beacon(frame)
        elif frame.type == "ACK":
            self.process_ack(frame)
        elif frame.type == "SYN":
            self.process_syn(frame)
        elif frame.type == "DATA":
            self.process_data(frame)
        else:
            self.logger.warning(f"Неизвестный тип фрейма: {frame.type}")
            print(f"Неизвестный тип фрейма: {frame.type}")
    
    def process_beacon(self, frame: Frame):
        """Обработка BEACON фрейма"""
        # Обновляем информацию об отправителе в локальной карте
        position, timestamp = self.deserialize_position(frame.payload)
        self.local_map[frame.sender_id] = (position, timestamp)
        
        # Отправляем подтверждение
        ack_frame = Frame("ACK", self.node_id, self.serialize_position())
        self.network.transmit_frame(ack_frame, self.node_id, frame.sender_id)
        
        # Обновляем таблицу маршрутизации
        self.update_routing_table(frame.sender_id, frame.sender_id, 1.0)
    
    def process_ack(self, frame: Frame):
        """Обработка ACK фрейма"""
        position, timestamp = self.deserialize_position(frame.payload)
        self.local_map[frame.sender_id] = (position, timestamp)
        
        # Обновляем таблицу маршрутизации
        self.update_routing_table(frame.sender_id, frame.sender_id, 1.0)
    
    def process_syn(self, frame: Frame):
        """Обработка SYN фрейма (запрос на подключение)"""
        position, timestamp = self.deserialize_position(frame.payload)
        distance = self.state.position.distance_to(position)
        
        if distance <= R:
            # Узел в зоне покрытия, отправляем ACK
            ack_frame = Frame("ACK", self.node_id, self.serialize_position())
            self.network.transmit_frame(ack_frame, self.node_id, frame.sender_id)
            
            # Добавляем в локальную карту
            self.local_map[frame.sender_id] = (position, timestamp)
            
            # Обновляем таблицу маршрутизации
            self.update_routing_table(frame.sender_id, frame.sender_id, 1.0)
    
    def process_data(self, frame: Frame):
        """Обработка DATA фрейма"""
        if frame.sender_id == self.node_id:
            return  # Игнорируем свои собственные сообщения
        
        message = frame.payload.decode()
        self.logger.info(f"\n[Сообщение от узла {frame.sender_id}]: {message}")
    
    def update_routing_table(self, node_id: int, next_hop: int, metric: float):
        """Обновление таблицы маршрутизации"""
        expire_time = datetime.now() + timedelta(seconds=60)  # 1 минута
        
        if node_id in self.routing_table:
            # Обновляем существующую запись, если метрика лучше
            if metric < self.routing_table[node_id].metric:
                self.routing_table[node_id] = RoutingEntry(node_id, next_hop, expire_time, metric)
        else:
            # Добавляем новую запись
            self.routing_table[node_id] = RoutingEntry(node_id, next_hop, expire_time, metric)
    
    def serialize_position(self) -> bytes:
        """Сериализация позиции и времени для передачи в фрейме"""
        return f"{self.state.position.x},{self.state.position.y},{datetime.now().timestamp()}".encode()
    
    def deserialize_position(self, data: bytes) -> Tuple[Position, datetime]:
        """Десериализация позиции и времени из фрейма"""
        parts = data.decode().split(",")
        x, y, timestamp = float(parts[0]), float(parts[1]), float(parts[2])
        return Position(x, y), datetime.fromtimestamp(timestamp)
    
    def send_command(self, command: str):
        """Отправка команды на узел для выполнения"""
        self.message_queue.put(command)
    
    def stop(self):
        """Остановка работы узла"""
        self.running = False
