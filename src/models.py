from dataclasses import dataclass, field
from src.SimulatorDateTime import SimulatorDateTime as datetime
from typing import Optional
import math
import json
import struct
import zlib

@dataclass
class Position:
    """Класс для представления позиции узла в 2D-пространстве"""
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        """Вычисление евклидова расстояния до другой позиции"""
        return math.hypot(self.x - other.x, self.y - other.y)
    
    def serialize(self) -> bytes:
        """Сериализация позиции в bytes"""
        return struct.pack('!ff', self.x, self.y)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Position':
        """Десериализация позиции из bytes"""
        x, y = struct.unpack('!ff', data)
        return cls(x, y)

@dataclass
class NodeState:
    """Состояние узла сети, включая позицию и параметры движения"""
    position: Position
    velocity: float = 0.0
    direction: float = 0.0  # угол в радианах (0 - восток, π/2 - север)
    last_update: datetime = field(default_factory=datetime.now)
    
    def move(self, delta_t: float) -> None:
        """Обновление позиции узла с учётом движения"""
        dx = self.velocity * math.cos(self.direction) * delta_t
        dy = self.velocity * math.sin(self.direction) * delta_t
        self.position.x += dx
        self.position.y += dy
        self.last_update = datetime.now()

@dataclass
class RoutingEntry:
    """Запись в таблице маршрутизации"""
    destination: int          # ID целевого узла
    next_hop: int             # ID следующего узла на пути
    expire_time: datetime     # Время истечения срока действия записи
    metric: float             # Метрика маршрута - комбинация качества связи и стабильности
    is_direct: bool = True    # Прямое ли это соединение
    
    def is_expired(self) -> bool:
        """Проверка, истек ли срок действия записи"""
        return datetime.now() >= self.expire_time
    
    def time_to_live(self) -> float:
        """Оставшееся время жизни записи в секундах"""
        return (self.expire_time - datetime.now()).total_seconds()

class Frame:
    """Класс для представления сетевого фрейма"""
    
    # Поддерживаемые типы фреймов
    BEACON = 'BEACON'    # Фрейм для обнаружения соседей
    ACK = 'ACK'          # Подтверждение получения
    RREQ = 'RREQ'        # Запрос маршрута (Route Request)
    RREP = 'RREP'        # Ответ маршрута (Route Reply)
    DATA = 'DATA'        # Пользовательские данные
    ERROR = 'ERROR'      # Фрейм ошибки
    
    def __init__(
        self,
        frame_type: str,
        sender_id: int,
        destination_id: Optional[int] = None,
        payload: bytes = b'',
        ttl: int = 10,
        **kwargs
    ) -> None:
        self.type = frame_type
        self.sender_id = sender_id
        self.destination_id = destination_id
        self.payload = payload
        self.ttl = ttl                  # Time To Live (макс. число прыжков)
        self.hop_count = 0              # Текущее число прыжков
        self.timestamp = datetime.now()
        self.metadata = kwargs          # Дополнительные метаданные
        
        # Автоматически вычисляем CRC при создании
        self.crc = self._calculate_crc()
    
    def __str__(self) -> str:
        return (f"Frame(type={self.type}, sender={self.sender_id}, "
                f"dest={self.destination_id}, hops={self.hop_count}, "
                f"size={len(self.payload)} bytes)")
    
    def __lt__(self, other: 'Frame') -> bool:
        """Сравнение для приоритетной очереди"""
        return self.timestamp < other.timestamp
    
    def _calculate_crc(self) -> int:
        """Вычисление контрольной суммы фрейма"""
        data = (
            self.type.encode() +
            str(self.sender_id).encode() +
            (str(self.destination_id).encode() if self.destination_id else b'') +
            self.payload
        )
        return zlib.crc32(data)
    
    def verify_crc(self) -> bool:
        """Проверка целостности фрейма"""
        return self.crc == self._calculate_crc()
    
    def increment_hop(self) -> bool:
        """Увеличение счетчика прыжков и проверка TTL"""
        self.hop_count += 1
        return self.hop_count < self.ttl
    
    def serialize(self) -> bytes:
        """Сериализация фрейма для передачи по сети"""
        metadata = json.dumps(self.metadata).encode() if self.metadata else b''
        header = struct.pack(
            '!8siiiiii',
            self.type.encode('ascii'),
            self.sender_id,
            self.destination_id if self.destination_id is not None else -1,
            self.ttl,
            self.hop_count,
            int(self.timestamp.timestamp()),
            len(metadata)
        )
        return header + metadata + self.payload
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Frame':
        """Десериализация фрейма из bytes"""
        try:
            header = data[:40]
            type_, sender_id, dest_id, ttl, hop_count, timestamp, meta_len = struct.unpack('!8siiiiii', header)
            
            frame_type = type_.decode('ascii').strip('\x00')
            destination_id = dest_id if dest_id != -1 else None
            timestamp = datetime.fromtimestamp(timestamp)
            
            metadata = {}
            if meta_len > 0:
                meta_data = data[40:40+meta_len]
                metadata = json.loads(meta_data.decode())
            
            payload = data[40+meta_len:]
            
            return cls(
                frame_type=frame_type,
                sender_id=sender_id,
                destination_id=destination_id,
                payload=payload,
                ttl=ttl,
                hop_count=hop_count,
                timestamp=timestamp,
                **metadata
            )
        except Exception as e:
            raise ValueError(f"Ошибка десериализации фрейма: {str(e)}")
    
    # Фабричные методы для создания стандартных фреймов
    @classmethod
    def create_beacon(cls, sender_id: int, payload: bytes = b'') -> 'Frame':
        """Создание BEACON фрейма"""
        return cls(cls.BEACON, sender_id, payload=payload)
    
    @classmethod
    def create_ack(cls, sender_id: int, payload: bytes = b'') -> 'Frame':
        """Создание ACK фрейма"""
        return cls(cls.ACK, sender_id, payload=payload)
    
    @classmethod
    def create_rreq(
        cls,
        sender_id: int,
        target_id: int,
        hop_count: int = 0,
        max_hops: int = 7
    ) -> 'Frame':
        """Создание Route Request (RREQ) фрейма"""
        return cls(
            cls.RREQ,
            sender_id,
            payload=json.dumps({
                'target_id': target_id,
                'hop_count': hop_count,
                'max_hops': max_hops
            }).encode(),
            ttl=max_hops
        )
    
    @classmethod
    def create_rrep(
        cls,
        sender_id: int,
        target_id: int,
        hop_count: int,
        route_metric: float = 1.0
    ) -> 'Frame':
        """Создание Route Reply (RREP) фрейма"""
        return cls(
            cls.RREP,
            sender_id,
            destination_id=target_id,
            payload=json.dumps({
                'hop_count': hop_count,
                'metric': route_metric
            }).encode()
        )
    
    @classmethod
    def create_data(
        cls,
        sender_id: int,
        destination_id: int,
        payload: bytes
    ) -> 'Frame':
        """Создание DATA фрейма"""
        return cls(
            cls.DATA,
            sender_id,
            destination_id=destination_id,
            payload=payload,
            ttl=20  # Больший TTL для данных
        )
    
    @classmethod
    def create_error(
        cls,
        sender_id: int,
        destination_id: int,
        error_code: int,
        error_msg: str
    ) -> 'Frame':
        """Создание ERROR фрейма"""
        return cls(
            cls.ERROR,
            sender_id,
            destination_id=destination_id,
            payload=json.dumps({
                'code': error_code,
                'message': error_msg
            }).encode()
        )
