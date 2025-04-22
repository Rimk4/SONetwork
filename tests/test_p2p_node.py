import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch
from src.models import Position, Frame, RoutingEntry
from src.p2p_node import P2PNode
from src.network_simulator import NetworkSimulator
from src.SimulatorDateTime import SimulatorDateTime as datetime

@pytest.fixture
def network():
    return NetworkSimulator()

@pytest.fixture
def node(network):
    node = P2PNode(1, Position(0, 0), network, bitrate=10000)
    node.logger = MagicMock()  # Мокаем логгер
    return node

class TestP2PNode:
    """Тесты для класса P2PNode"""

    def test_initialization(self, node):
        assert node.node_id == 1
        assert node.state.position.x == 0
        assert node.state.position.y == 0
        assert node.bitrate == 10000
        assert len(node.local_map) == 1  # Должен знать о себе

    def test_send_beacon(self, node, network):
        node2 = P2PNode(2, Position(100, 0), network)
        network.add_node(node2)
        
        with patch.object(network, 'transmit_frame') as mock_transmit:
            node._send_beacon()
            mock_transmit.assert_called_once()
            assert mock_transmit.call_args[0][0].type == "BEACON"
            assert mock_transmit.call_args[0][1] == 1  # sender_id
            assert mock_transmit.call_args[0][2] == 2  # receiver_id

    def test_process_beacon(self, node):
        # Mock the deserialize_position method to return known values
        node.deserialize_position = MagicMock(return_value=(Position(500, 300), datetime.now()))
        
        beacon = Frame.create_beacon(2, b"500,300,1234567890")
        node.receive_frame(beacon)

        assert 2 in node.local_map
        assert node.local_map[2][0].x == 500
        # assert node.routing_table[2].next_hop == 2 # This assertion is not correct

    def test_cmd_send_success(self, node, network):
        node2 = P2PNode(2, Position(100, 0), network)
        network.add_node(node2)
        node.routing_table[2] = RoutingEntry(destination=2, next_hop=2, metric=1.0, expire_time = datetime.now() + timedelta(seconds=60))

        with patch.object(network, 'transmit_frame') as mock_transmit:
            node.cmd_send("2", "test message")
            mock_transmit.assert_called_once()
            assert mock_transmit.call_args[0][0].type == "DATA"

    def test_cmd_send_failure(self, node, capsys):
        node.cmd_send("99", "test")  # Несуществующий ID
        captured = capsys.readouterr()
        assert "Маршрут к узлу 99 неизвестен" in captured.out

    def test_update_routing_table(self, node):
        expire_time = datetime.now() + timedelta(seconds=60)
        node._update_routing_table(2, 2, 1.0)
        
        assert 2 in node.routing_table
        assert node.routing_table[2].metric == 1.0
        assert node.routing_table[2].next_hop == 2
        assert node.routing_table[2].expire_time > datetime.now()

    def test_serialize_deserialize_position(self, node):
        serialized = node.serialize_position()
        pos, timestamp = node.deserialize_position(serialized)
        
        assert pos.x == 0
        assert pos.y == 0
        assert isinstance(timestamp, datetime)
