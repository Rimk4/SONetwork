import pytest
from datetime import datetime
from src.models import Position, NodeState

class TestPosition:
    def test_distance(self):
        p1 = Position(0, 0)
        p2 = Position(3, 4)
        assert p1.distance_to(p2) == 5.0

class TestNodeState:
    @pytest.fixture
    def node_state(self):
        return NodeState(Position(0, 0), velocity=10, direction=0)

    def test_movement(self, node_state):
        node_state.move(1.0)  # 1 секунда
        assert node_state.position.x == 10.0
        assert node_state.position.y == 0.0
        assert isinstance(node_state.last_update, datetime)
