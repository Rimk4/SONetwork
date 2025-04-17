from io import StringIO
import pytest
from src.cli import interactive_control
from unittest.mock import MagicMock, patch, call

@pytest.fixture
def mock_network():
    """Фикстура для мок-объекта сети с поддержкой stop_simulation"""
    network = MagicMock()
    network._should_stop = False
    
    # Реализуем side_effect для stop_simulation
    def stop_simulation_side_effect():
        network._should_stop = True
        for node in network.nodes.values():
            node.stop()
    
    network.stop_simulation.side_effect = stop_simulation_side_effect
    return network

def test_single_node_exit(mock_network):
    """Тест выхода при одном узле"""
    mock_node = MagicMock()
    mock_network.nodes = {1: mock_node}
    
    with patch('builtins.input', return_value='exit'):
        interactive_control(mock_network)

        # Проверяем, что stop_simulation был вызван
        mock_network.stop_simulation.assert_called_once()
        mock_node.stop.assert_called_once()
        mock_node.join.assert_called_once()

@pytest.mark.parametrize("command,expected", [
    ("test command", "test command"),
    ("another cmd", "another cmd"),
])
def test_command_handling(mock_network, command, expected):
    """Тест обработки команд с параметризацией"""
    mock_node = MagicMock()
    mock_network.nodes = {1: mock_node}
    
    with patch('builtins.input', side_effect=[command, 'exit']):
        interactive_control(mock_network)
        
        mock_node.send_command.assert_called_once_with(expected)

def test_switch_node(mock_network):
    """Тест переключения узлов"""
    mock_node1 = MagicMock()
    mock_node2 = MagicMock()
    mock_network.nodes = {1: mock_node1, 2: mock_node2}
    
    input_sequence = ['switch', '2', 'exit']
    with patch('builtins.input', side_effect=input_sequence):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            interactive_control(mock_network)
            
            output = fake_out.getvalue()
            assert "Доступные узлы: [1, 2]" in output
            assert "Переключено на узел 2" in output

def test_kill_node(mock_network):
    """Тест удаления узла с проверкой последовательности команд"""
    mock_node1 = MagicMock()
    mock_node2 = MagicMock()
    mock_network.nodes = {1: mock_node1, 2: mock_node2}
    
    # Задаем поведение remove_node: удаляем ноду из словаря
    def remove_node_side_effect(node_id):
        mock_network.nodes.pop(node_id)
    
    mock_network.remove_node.side_effect = remove_node_side_effect
    
    # Эмулируем последовательность команд: kill → exit
    with patch('builtins.input', side_effect=['kill', 'exit']):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            interactive_control(mock_network)
            
            output = fake_out.getvalue()
            assert "Удаляем узел 1..." in output

    # Проверяем, что remove_node был вызван с правильным аргументом
    mock_network.remove_node.assert_called_once_with(1)
    
    # Проверяем, что нода действительно удалена из словаря
    assert 1 not in mock_network.nodes
    
    # Проверяем вызовы после команды exit
    mock_node2.stop.assert_called_once()
    mock_node2.join.assert_called_once()

def test_keyboard_interrupt(mock_network):
    """Тест обработки KeyboardInterrupt"""
    mock_node = MagicMock()
    mock_network.nodes = {1: mock_node}
    
    with patch('builtins.input', side_effect=KeyboardInterrupt()):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            interactive_control(mock_network)
            
            output = fake_out.getvalue().strip()
            assert "Завершение работы..." in output

    # Проверяем вызов stop_simulation при прерывании
    mock_network.stop_simulation.assert_called_once()
    mock_node.stop.assert_called_once()
    mock_node.join.assert_called_once()
