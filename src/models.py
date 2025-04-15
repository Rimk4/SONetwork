from dataclasses import dataclass, field
from datetime import datetime
import math

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
