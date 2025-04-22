import time
from typing import List, Tuple

class CommandGenerator:
    """Класс генератора команд, вводимых мнимым пользователем"""
    def _generate_command_sequence(self) -> List[Tuple[str, float]]:
        """Генерирует последовательность всех возможных команд с задержками"""
        return [
            ("info", 0.5),
            ("scan", 1.0),
            ("nodes", 0.5),
            ("route", 1.0),
            ("send 2 test_message", 2.0),
            ("findroute 2", 1.5),
            ("log INFO", 0.5),
            ("switch", 1.0),
            ("visualize", 2.0),
            ("addnode 50 50", 1.5),
            ("moveto 30 30", 1.0),
            ("setvelocity 1.5 45", 1.0),
            ("record 2 5", 5.0),
            ("\n", 0.1),
            ("stop", 1.0),
            ("savecfg", 1.5),
            ("kill", 2.0),
            ("exit", 0)
        ]

def main():
    generator = CommandGenerator()
    commands = generator._generate_command_sequence()
    
    for command, delay in commands:
        print(command, flush=True)
        time.sleep(delay)

if __name__ == '__main__':
    main()
