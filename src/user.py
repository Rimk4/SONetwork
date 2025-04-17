import time
import random
from typing import Optional
from src.network_simulator import NetworkSimulator

class UserSimulator:
    def __init__(self, network: NetworkSimulator):
        self.network = network
        self.current_node_id: Optional[int] = next(iter(network.nodes)) if network.nodes else None
        self.commands = [
            ("info", 0.5),
            ("scan", 1.2),
            ("nodes", 0.3),
            ("switch", 1.0),
            ("send", 2.0),
            ("route", 1.5),
            ("kill", 3.0)
        ]
    
    def run(self, duration: float = 60.0):
        """Запускает симуляцию пользователя на указанное время (в секундах)"""
        start_time = time.time()
        
        while time.time() - start_time < duration:
            if not self.current_node_id or not self.network.nodes:
                print("Нет активных узлов - симуляция завершена")
                break
            
            # Выбираем случайную команду с учетом весов
            cmd, delay = random.choice(self.commands)
            
            # Имитируем ввод команды
            self._execute_command(cmd)
            
            # Ждем перед следующей командой
            time.sleep(delay)
        
        # Завершаем работу
        print("Симуляция завершена - выход")
        self._execute_command("exit")
    
    def _execute_command(self, cmd: str):
        """Имитирует выполнение команды"""
        print(f"node_{self.current_node_id}> {cmd}")  # Эмулируем prompt
        
        if cmd.lower() in ("exit", "q"):
            for node in self.network.nodes.values():
                node.stop()
                node.join()
            return
        
        if cmd.lower() == "switch":
            available_nodes = list(self.network.nodes.keys())
            if len(available_nodes) > 1:
                # Выбираем случайный узел, отличный от текущего
                new_id = random.choice([n for n in available_nodes if n != self.current_node_id])
                self.current_node_id = new_id
                print(f"Переключено на узел {new_id}")
            return
        
        if cmd.lower() == "kill" and len(self.network.nodes) > 1:
            # Удаляем текущий узел
            node = self.network.nodes[self.current_node_id]
            node.stop()
            node.join()
            self.network.remove_node(self.current_node_id)
            
            # Переключаемся на случайный оставшийся узел
            self.current_node_id = next(iter(self.network.nodes))
            print(f"Узел удален, переключено на {self.current_node_id}")
            return
        
        # Отправляем команду текущему узлу
        if self.current_node_id in self.network.nodes:
            self.network.nodes[self.current_node_id].send_command(cmd)


def simulate_user(network: NetworkSimulator, duration: float = 60.0):
    """Функция для запуска симуляции пользователя"""
    print("\n=== Запуск симуляции пользователя ===")
    user = UserSimulator(network)
    user.run(duration)
