import json
import os
import logging
import queue
import threading
import time
import math
from datetime import timedelta
from src.SimulatorDateTime import SimulatorDateTime as datetime
from typing import Dict, Tuple, Optional, List
from src.models import Position, Frame, NodeState, RoutingEntry
from src.constants import T_SCAN, T_TIMEOUT, T_SLEEP_MIN, T_SLEEP_MAX, LOG_DIR, R

class P2PNode(threading.Thread):
    """Класс, реализующий узел P2P-сети с улучшенной маршрутизацией"""
    
    def __init__(self, node_id: int, position: Position, network: 'NetworkSimulator', 
                 velocity: float = 0.0, direction: float = 0.0, bitrate: int = 5000):
        super().__init__(daemon=True)
        self.node_id = node_id
        self.state = NodeState(position, velocity, direction)
        self.network = network
        self.bitrate = bitrate
        # Таблица маршрутизации (destination -> RoutingEntry)
        self.routing_table: Dict[int, RoutingEntry] = {}
        # Локальная карта узлов (ID -> (position, last_update))
        self.local_map: Dict[int, Tuple[Position, datetime]] = {}
        # Очередь сообщений для команд управления
        self.message_queue = queue.Queue()
        # Очередь для отложенных фреймов (когда маршрут временно недоступен)
        self.delayed_frames: Dict[int, List[Frame]] = {}
        # Флаг работы узла
        self.running = True
        # Команды управления узлом
        self.commands = {
            "info": self.cmd_info,
            "scan": self.cmd_scan,
            "send": self.cmd_send,
            "route": self.cmd_show_routes,
            "nodes": self.cmd_show_nodes,
            "help": self.cmd_help,
            "log": self.cmd_set_loglvl,
            "findroute": self.cmd_find_route,
        }

        # Настройка логгера для узла
        self._setup_logger()
        # Параметры маршрутизации
        self.route_discovery_timeout = 5.0  # сек
        self.max_hops = 10  # максимальное количество прыжков
        self.route_ttl = 60.0  # время жизни маршрута (сек)
        self.beacon_interval = T_SCAN
        # Инициализация локальной карты
        self.local_map[self.node_id] = (self.state.position, datetime.now())
        
        print(f"P2PNode: Создан узел {self.node_id} на позиции ({position.x:.1f}, {position.y:.1f})")

    def _setup_logger(self):
        """Настройка логгера для узла"""
        self.logger = logging.getLogger(f"Node-{self.node_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # Создаем директорию для логов, если ее нет
        os.makedirs(LOG_DIR, exist_ok=True)
        
        log_file = os.path.join(LOG_DIR, f"node_{self.node_id}.log")
        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def run(self):
        """Основной цикл работы узла"""
        last_beacon = datetime.now()
        
        while self.running:
            current_time = datetime.now()
            
            # 1. Очистка устаревших записей
            self._cleanup_expired_entries(current_time)
            
            # 2. Обновление позиции
            self._update_position(current_time)
            
            # 3. Периодическая рассылка beacon-сообщений
            if (current_time - last_beacon).total_seconds() >= self.beacon_interval:
                self._send_beacon()
                last_beacon = current_time
                
                # Дополнительно проверяем отложенные фреймы
                # self._check_delayed_frames()
            
            # 4. Обработка команд управления
            self._process_commands()
            
            # 5. Короткая пауза
            time.sleep(0.1)

    def _cleanup_expired_entries(self, current_time: datetime):
        """Очистка устаревших записей в таблицах"""
        # Очистка локальной карты
        expired_nodes = [
            node_id for node_id, (_, last_update) in self.local_map.items()
            if (current_time - last_update).total_seconds() > T_TIMEOUT
        ]
        for node_id in expired_nodes:
            del self.local_map[node_id]
            self.logger.debug(f"Узел {node_id} удален из local_map (таймаут)")
            
            # Если узел был в таблице маршрутизации, удаляем и его оттуда
            if node_id in self.routing_table:
                del self.routing_table[node_id]
                self.logger.debug(f"Маршрут к узлу {node_id} удален из routing_table")
        
        # Очистка устаревших маршрутов из таблицы маршрутизации
        expired_routes = [
            node_id for node_id, entry in self.routing_table.items()
            if entry.expire_time <= current_time
        ]
        for node_id in expired_routes:
            del self.routing_table[node_id]
            self.logger.debug(f"Маршрут к узлу {node_id} удален (истек TTL)")

    def _update_position(self, current_time: datetime):
        """Обновление позиции узла"""
        delta_t = (current_time - self.state.last_update).total_seconds()
        if delta_t > 0:
            self.state.move(delta_t)
            self.local_map[self.node_id] = (self.state.position, current_time)

    def _send_beacon(self):
        """Рассылка beacon-сообщений соседям"""
        beacon = Frame.create_beacon(
            sender_id=self.node_id,
            payload=self.serialize_position()
        )
        
        # Рассылка beacon всем известным узлам
        for node_id in self.network.nodes:
            if node_id != self.node_id:
                self.network.transmit_frame(beacon, self.node_id, node_id)
        
        self.logger.debug(f"Отправлен BEACON всем узлам")

    def _check_delayed_frames(self):
        """Проверка отложенных фреймов (для которых не было маршрута)"""
        completed = []
        
        for target_id, frames in self.delayed_frames.items():
            if target_id in self.routing_table:
                # Маршрут появился, отправляем все отложенные фреймы
                next_hop = self.routing_table[target_id].next_hop
                for frame in frames:
                    if self.network.transmit_frame(frame, self.node_id, next_hop):
                        self.logger.info(f"Отправлен отложенный фрейм для {target_id}")
                
                completed.append(target_id)
        
        # Удаляем отправленные фреймы
        for target_id in completed:
            del self.delayed_frames[target_id]

    def _process_commands(self):
        """Обработка команд из очереди"""
        try:
            cmd = self.message_queue.get_nowait()
            self.process_command(cmd)
        except queue.Empty:
            pass
    
    def process_command(self, cmd: str):
        """Обработка команды управления"""
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
                self.logger.error(f"Ошибка выполнения команды {command}: {str(e)}")
        else:
            print(f"Неизвестная команда: {command}. Введите 'help' для списка команд.")

    def cmd_info(self):
        """Вывод информации о текущем узле"""
        print(f"\n=== Информация об узле {self.node_id} ===")
        print(f"Позиция: ({self.state.position.x:.1f}, {self.state.position.y:.1f})")
        print(f"Скорость: {self.state.velocity:.1f} м/с, направление: {math.degrees(self.state.direction):.1f}°")
        print(f"Битрейт: {self.bitrate} бит/с")
        print(f"Известно узлов: {len(self.local_map)}")
        print(f"Маршрутов в таблице: {len(self.routing_table)}")
        # print(f"Отложенных фреймов: {sum(len(f) for f in self.delayed_frames.values())}")

    def cmd_scan(self):
        """Инициировать сканирование соседей"""
        print(f"\nУзел {self.node_id} запускает сканирование...")
        self._send_beacon()

    def cmd_send(self, target_id: str, *message_parts: str):
        """Отправить сообщение другому узлу"""
        try:
            target_node_id = int(target_id)
            message = " ".join(message_parts)
            
            if target_node_id == self.node_id:
                print("Нельзя отправить сообщение самому себе!")
                return
            
            frame = Frame.create_data(
                sender_id=self.node_id,
                destination_id=target_node_id,
                payload=message.encode()
            )
            
            self._send_frame(frame, target_node_id)

        except ValueError:
            print("Неверный ID узла!")
    
    def _send_frame(self, frame: Frame, target_id: int):
        """Отправка фрейма с обработкой маршрутизации"""
        if target_id in self.routing_table:
            # Маршрут известен - отправляем
            next_hop = self.routing_table[target_id].next_hop
            if self.network.transmit_frame(frame, self.node_id, next_hop):
                self.logger.info(f"Фрейм отправлен к {target_id} через {next_hop}")
            else:
                self.logger.warning(f"Ошибка передачи фрейма к {target_id}")
                self._initiate_route_discovery(target_id)
                self._delay_frame(frame, target_id)
        else:
            # Маршрут неизвестен - инициируем поиск и откладываем фрейм
            print(f"Маршрут к узлу {target_id} неизвестен. Инициирую поиск...")
            self._initiate_route_discovery(target_id)
            self._delay_frame(frame, target_id)

    def _delay_frame(self, frame: Frame, target_id: int):
        """Добавление фрейма в очередь отложенных"""
        if target_id not in self.delayed_frames:
            self.delayed_frames[target_id] = []
        self.delayed_frames[target_id].append(frame)
        self.logger.info(f"Фрейм для {target_id} отложен (ожидание маршрута)")

    def _initiate_route_discovery(self, target_id: int):
        """Инициирование поиска маршрута (AODV-like)"""
        if target_id in self.local_map:
            # Узел в локальной карте, но не в таблице маршрутизации
            rreq = Frame.create_rreq(
                sender_id=self.node_id,
                target_id=target_id,
                hop_count=0,
                max_hops=self.max_hops
            )
            
            # Рассылка RREQ всем соседям
            for neighbor_id in self._get_neighbors():
                self.network.transmit_frame(rreq, self.node_id, neighbor_id)
            
            self.logger.info(f"Инициирован поиск маршрута к {target_id}")

    def _get_neighbors(self) -> List[int]:
        """Получение списка соседей в радиусе R"""
        neighbors = []
        
        for node_id in self.local_map:
            if node_id != self.node_id:
                neighbors.append(node_id)
        
        return neighbors

    def cmd_show_routes(self):
        """Показать таблицу маршрутизации"""
        print("\n=== Таблица маршрутизации ===")
        if not self.routing_table:
            print("Таблица маршрутизации пуста")
            return

        print(f"{'Цель':<8}{'След. прыжок':<12}{'Метрика':<10}{'Истекает через':<15}")
        for node_id, entry in self.routing_table.items():
            expires_in = (entry.expire_time - datetime.now()).total_seconds()
            print(f"{node_id:<8}{entry.next_hop:<12}{entry.metric:<10.1f}{expires_in:.1f} сек")

    def cmd_show_nodes(self):
        """Показать известные узлы"""
        print("\n=== Известные узлы ===")
        if not self.local_map:
            print("Локальная карта пуста")
            return

        print(f"{'ID узла':<10}{'Позиция (x,y)':<25}{'Обновлено':<20}")
        for node_id, (pos, last_update) in self.local_map.items():
            age = (datetime.now() - last_update).total_seconds()
            coords = f'({pos.x:.1f}, {pos.y:.1f})'
            print(f"{node_id:<10}{coords:<25}{age:.1f} сек назад")

    def cmd_find_route(self, target_id: str):
        """Найти маршрут к указанному узлу"""
        try:
            target_node_id = int(target_id)
            
            if target_node_id == self.node_id:
                print("Это ваш собственный ID!")
                return
            
            if target_node_id in self.routing_table:
                entry = self.routing_table[target_node_id]
                expires_in = (entry.expire_time - datetime.now()).total_seconds()
                print(f"Маршрут к узлу {target_node_id}:")
                print(f"Следующий прыжок: {entry.next_hop}")
                print(f"Метрика: {entry.metric:.1f}")
                print(f"Истекает через: {expires_in:.1f} сек")
            else:
                print(f"Маршрут к узлу {target_node_id} неизвестен. Инициирую поиск...")
                self._initiate_route_discovery(target_node_id)

        except ValueError:
            print("Неверный ID узла!")
    
    def cmd_help(self):
        """Показать справку по командам"""
        print("\n=== Доступные команды ===")
        print("info - информация об узле")
        print("scan - сканировать соседей")
        print("send <id> <msg> - отправить сообщение")
        print("route - показать таблицу маршрутизации")
        print("nodes - показать известные узлы")
        print("log <level> - изменить уровень логгирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
        print("record [fps] [duration] - начать запись (например: record 5 10 - 5 FPS в течение 10 сек)")
        print("stop - остановить запись досрочно")
        print("visualize - скриншот текущей сети от лица текущего узла")
        print("savecfg - сохранить текущую конфигурацию")
        print("findroute <id> - найти маршрут к узлу")
        print("help - показать эту справку")

    def cmd_set_loglvl(self, level: str):
        """Установка уровня логгирования"""
        level = level.upper()
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        if level in levels:
            self.logger.setLevel(levels[level])
            print(f"Уровень логгирования установлен на {level}")
        else:
            print("Неверный уровень. Допустимые: DEBUG, INFO, WARNING, ERROR, CRITICAL")

    def receive_frame(self, frame: Frame):
        """Обработка входящего фрейма"""
        self.logger.debug(f"Получен фрейм {frame.type} от {frame.sender_id}")
        
        # Обновляем информацию об отправителе (если есть данные о позиции)
        if frame.type in ["BEACON", "ACK", "SYN"]:
            try:
                pos, timestamp = self.deserialize_position(frame.payload)
                self.local_map[frame.sender_id] = (pos, timestamp)
            except:
                pass
        
        # Обработка по типу фрейма
        if frame.type == "BEACON":
            self._process_beacon(frame)
        elif frame.type == "ACK":
            self._process_ack(frame)
        elif frame.type == "RREQ":
            self._process_rreq(frame)
        elif frame.type == "RREP":
            self._process_rrep(frame)
        elif frame.type == "DATA":
            self._process_data(frame)
        else:
            self.logger.warning(f"Неизвестный тип фрейма: {frame.type}")

    def _process_beacon(self, frame: Frame):
        """Обработка BEACON фрейма"""
        # Отправляем подтверждение
        ack = Frame.create_ack(
            sender_id=self.node_id,
            payload=self.serialize_position()
        )
        self.network.transmit_frame(ack, self.node_id, frame.sender_id)
        
        # Обновляем таблицу маршрутизации
        self._update_routing_table(frame.sender_id, frame.sender_id, 1.0)

    def _process_ack(self, frame: Frame):
        """Обработка ACK фрейма"""
        # Просто обновляем таблицу маршрутизации
        self._update_routing_table(frame.sender_id, frame.sender_id, 1.0)

    def _process_rreq(self, frame: Frame):
        """Обработка Route Request (RREQ)"""
        try:
            payload_dict = json.loads(frame.payload.decode())
        except Exception as e:
            self.logger.error(f"Ошибка декодирования payload: {e}")
            return

        target_id = payload_dict['target_id']
        hop_count = payload_dict['hop_count'] + 1
        
        # Если это наш RREQ (отправили сами) - игнорируем
        if frame.sender_id == self.node_id:
            return
        
        # Если мы целевой узел - отправляем RREP
        if target_id == self.node_id:
            rrep = Frame.create_rrep(
                sender_id=self.node_id,
                target_id=frame.sender_id,
                hop_count=hop_count
            )
            
            # Отправляем по обратному маршруту
            next_hop = frame.sender_id
            self.network.transmit_frame(rrep, self.node_id, next_hop)
            return
        
        # Если у нас есть маршрут к цели - отправляем RREP
        if target_id in self.routing_table:
            rrep = Frame.create_rrep(
                sender_id=self.node_id,
                target_id=frame.sender_id,
                hop_count=hop_count + self.routing_table[target_id].metric
            )
            
            next_hop = frame.sender_id
            self.network.transmit_frame(rrep, self.node_id, next_hop)
            return
        
        # Если превышено максимальное число прыжков - отбрасываем
        if hop_count >= payload_dict['max_hops']:
            self.logger.debug(f"Отброшен RREQ для {target_id} (max_hops достигнут)")
            return
        
        # Пересылаем RREQ дальше
        new_rreq = Frame.create_rreq(
            sender_id=frame.sender_id,
            target_id=target_id,
            hop_count=hop_count,
            max_hops=payload_dict['max_hops']
        )
        
        # Рассылаем всем соседям, кроме отправителя
        for neighbor_id in self._get_neighbors():
            if neighbor_id != frame.sender_id:
                self.network.transmit_frame(new_rreq, self.node_id, neighbor_id)

    def _process_rrep(self, frame: Frame):
        """Обработка Route Reply (RREP)"""
        try:
            payload_dict = json.loads(frame.payload.decode())
        except Exception as e:
            self.logger.error(f"Ошибка декодирования payload: {e}")
            return

        target_id = payload_dict['target_id']
        hop_count = payload_dict['hop_count']
        
        # Если мы целевой узел - обновляем таблицу маршрутизации
        if target_id == self.node_id:
            # Метрика = количеству прыжков
            self._update_routing_table(
                frame.sender_id,
                frame.sender_id,
                hop_count
            )
            return
        
        # Пересылаем RREP дальше по маршруту
        if target_id in self.routing_table:
            next_hop = self.routing_table[target_id].next_hop
            
            # Обновляем метрику (увеличиваем на 1 прыжок)
            new_rrep = Frame.create_rrep(
                sender_id=self.node_id,
                target_id=target_id,
                hop_count=hop_count + 1
            )
            
            self.network.transmit_frame(new_rrep, self.node_id, next_hop)
            
            # Обновляем свою таблицу маршрутизации
            self._update_routing_table(
                frame.sender_id,
                frame.sender_id,
                hop_count
            )

    def _process_data(self, frame: Frame):
        """Обработка DATA фрейма"""
        # Если фрейм адресован нам - обрабатываем
        if frame.destination_id == self.node_id:
            message = frame.payload.decode()
            print(f"\n[Сообщение от {frame.sender_id}]: {message}")
            self.logger.info(f"Получено сообщение от {frame.sender_id}: {message}")
            return
        
        # Иначе пытаемся переслать дальше
        if frame.destination_id in self.routing_table:
            next_hop = self.routing_table[frame.destination_id].next_hop
            self.network.transmit_frame(frame, self.node_id, next_hop)
        else:
            self.logger.warning(f"Неизвестный маршрут для {frame.destination_id}, фрейм отброшен")

    def _update_routing_table(self, node_id: int, next_hop: int, metric: float):
        """Обновление таблицы маршрутизации"""
        now = datetime.now()
        expire_time = now + timedelta(seconds=self.route_ttl)
        
        # Если маршрут уже есть - обновляем только если новый лучше
        if node_id in self.routing_table:
            current_entry = self.routing_table[node_id]
            
            # Обновляем если:
            # 1. Новый маршрут имеет лучшую метрику
            # 2. Старый маршрут истек
            if (metric < current_entry.metric or 
                current_entry.expire_time <= now):
                
                self.routing_table[node_id] = RoutingEntry(node_id, next_hop, expire_time, metric)
                self.logger.info(f"Обновлен маршрут к {node_id} через {next_hop} (метрика: {metric:.1f})")
        else:
            # Добавляем новый маршрут
            self.routing_table[node_id] = RoutingEntry(node_id, next_hop, expire_time, metric)
            self.logger.info(f"Добавлен маршрут к {node_id} через {next_hop} (метрика: {metric:.1f})")

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
        self.logger.info("Узел остановлен")
