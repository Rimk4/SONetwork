import atexit
import os
import readline
import shutil
import time
import random
import math
import threading
import queue
import logging
from dataclasses import dataclass, field
from typing import Dict, Tuple
from datetime import datetime, timedelta

# Константы из отчёта
R = 10000  # Радиус связи 10 км в метрах
V_MAX = 16.67  # Максимальная скорость 60 км/ч в м/с
BITRATE_RANGE = (32, 37000)  # Диапазон битрейтов (32 бит/с - 37 кбит/с)
SYN_SIZE = 16  # Размер SYN фрейма в байтах
ACK_SIZE = 8  # Размер ACK фрейма в байтах
DATA_FRAME_SIZE = 64  # Размер фрейма данных в байтах
T_SCAN = 5  # Интервал сканирования в секундах
T_TIMEOUT = 5  # Таймаут соединения в секундах
T_SLEEP_MIN = 10  # Минимальное время сна в секундах
T_SLEEP_MAX = 300  # Максимальное время сна в секундах

# Папка для логов
LOG_DIR = "logs"
TMP_DIR = "tmp"
HISTORY_FILE = "tmp/command_history.txt"  # File to store command history

@dataclass
class Position:
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

@dataclass
class NodeState:
    position: Position
    velocity: float = 0.0
    direction: float = 0.0  # угол в радианах
    last_update: datetime = field(default_factory=datetime.now)
    
    def move(self, delta_t: float):
        """Обновление позиции узла с учётом движения"""
        dx = self.velocity * math.cos(self.direction) * delta_t
        dy = self.velocity * math.sin(self.direction) * delta_t
        self.position.x += dx
        self.position.y += dy
        self.last_update = datetime.now()

@dataclass
class RoutingEntry:
    node_id: int
    next_hop: int
    expire_time: datetime
    metric: float  # комбинация качества связи и стабильности

class Frame:
    def __init__(self, frame_type: str, sender_id: int, payload: bytes = b'', crc: int = 0):
        self.type = frame_type
        self.sender_id = sender_id
        self.payload = payload
        self.crc = crc
        self.timestamp = datetime.now()

    def __str__(self):
        return f"Frame(type={self.type}, sender={self.sender_id}, size={len(self.payload)} bytes)"

    def __lt__(self, other):
        return self.timestamp < other.timestamp

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

class P2PNode(threading.Thread):
    """Класс, реализующий узел P2P-сети"""
    
    def __init__(self, node_id: int, position: Position, network: NetworkSimulator, 
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
        
        print(f"Создан узел {self.node_id} на позиции ({position.x:.1f}, {position.y:.1f})")
    
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
                print(f"Ошибка выполнения команды: {e}")
        else:
            print(f"Неизвестная команда: {command}. Введите 'help' для списка команд.")
    
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
        print(f"\nУзел {self.node_id} инициирует сканирование соседей...")
        self.scan_neighbors()
    
    def cmd_send(self, target_id: str, *message_parts: str):
        """Отправить сообщение другому узлу"""
        try:
            target_node_id = int(target_id)
            message = " ".join(message_parts)
            
            if target_node_id == self.node_id:
                print("Нельзя отправить сообщение самому себе!")
                return
            
            if target_node_id not in self.routing_table:
                print(f"Узел {target_node_id} не найден в таблице маршрутизации!")
                return
            
            # Создаем фрейм с сообщением
            frame = Frame("DATA", self.node_id, message.encode())
            next_hop = self.routing_table[target_node_id].next_hop
            
            if self.network.transmit_frame(frame, self.node_id, next_hop):
                print(f"Сообщение отправлено узлу {target_node_id} через {next_hop}")
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
            print(f"{node_id:<10}({pos.x:.1f}, {pos.y:.1f}){'':<10}{age:.1f} сек назад")
    
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

def interactive_control(network: NetworkSimulator):
    """Интерактивное управление узлами сети"""
    current_node_id = next(iter(network.nodes)) if network.nodes else None

    # Load command history
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)

    # Save command history on exit
    atexit.register(readline.write_history_file, HISTORY_FILE)
    
    while True:
        try:
            if current_node_id is None:
                cmd = input("> ").strip()
                if cmd.lower() in ("exit", "q"):
                    break
                print("Нет активных узлов в сети")
                continue
            
            prompt = f"node_{current_node_id}> "
            cmd = input(prompt).strip()
            
            if not cmd:
                continue

            if cmd:
                readline.add_history(cmd)
            
            if cmd.lower() in ("exit", "q"):
                break
            
            if cmd.lower() == "switch":
                # Переключение на другой узел
                print("Доступные узлы:", list(network.nodes.keys()))
                try:
                    new_id = int(input("Введите ID узла: "))
                    if new_id in network.nodes:
                        current_node_id = new_id
                        print(f"Переключено на узел {new_id}")
                    else:
                        print("Узел с таким ID не найден")
                except ValueError:
                    print("Неверный ID узла")
                continue
            
            if cmd.lower() == "kill":
                if len(network.nodes) <= 1:
                    print("Нельзя удалить последний узел в сети!")
                    continue
                
                print(f"Удаляем узел {current_node_id}...")
                # 1. Останавливаем узел
                network.nodes[current_node_id].stop()
                # 2. Ждем завершения потока
                network.nodes[current_node_id].join()
                # 3. Удаляем из сетевого симулятора
                network.remove_node(current_node_id)
                
                # Переключаемся на другой доступный узел
                current_node_id = next(iter(network.nodes))
                print(f"Переключено на узел {current_node_id}")
                continue

            # Отправляем команду текущему узлу
            network.nodes[current_node_id].send_command(cmd)
            
            # Даем время на обработку команды
            time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\nЗавершение работы...")
            break
    
    # Останавливаем все узлы
    for node in network.nodes.values():
        node.stop()
        node.join()

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
