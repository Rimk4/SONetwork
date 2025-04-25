# CLI Command Line Interface
import atexit
import math
import os
import random
import readline
import tempfile
import time
from typing import Optional
from src.models import Position
from src.FrameRecorder import FrameRecorder

class CLICommandHandler:
    """Класс для обработки команд CLI"""
    
    def __init__(self, network: 'NetworkSimulator') -> None:
        self.network = network
        self.current_node_id: Optional[int] = next(iter(network.nodes)) if network.nodes else None
        self.recorder = FrameRecorder(network)
        self.session_history_file = self._setup_history()
        self._register_cleanup()
        
        # Дополнительные команды управления сетью
        self.network_commands = {
            "switch": self._switch_node,
            "kill": self._kill_node,
            "screenshot": self._screenshot,
            "record": self._record,
            "stop": self._stop_recording,
            "savecfg": self._save_config,
            "addnode": self._add_node,
            "moveto": self._move_node,
            "setvelocity": self._set_velocity,
            "help": self._show_help,
        }

    def _setup_history(self) -> str:
        """Настройка истории команд"""
        temp_history = tempfile.NamedTemporaryFile(delete=False)
        temp_history.close()
        history_file = temp_history.name
        
        if os.path.exists(history_file):
            readline.read_history_file(history_file)
        
        # Настройка автодополнения
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")
        
        return history_file

    def _register_cleanup(self) -> None:
        """Регистрация функций очистки при выходе"""
        atexit.register(self._cleanup)
        atexit.register(lambda: readline.write_history_file(self.session_history_file))

    def _cleanup(self) -> None:
        """Очистка временных файлов"""
        try:
            os.unlink(self.session_history_file)
        except OSError:
            pass

    def _completer(self, text: str, state: int) -> Optional[str]:
        """Функция автодополнения команд"""
        commands = list(self.network_commands.keys()) + ["exit", "q"]
        matches = [cmd for cmd in commands if cmd.startswith(text.lower())]
        return matches[state] if state < len(matches) else None

    def run(self) -> None:
        """Основной цикл работы CLI"""
        self._show_help()
        
        while True:
            try:
                if self.current_node_id is None:
                    self._handle_no_nodes_mode()
                    continue
                
                cmd = input(f"node_{self.current_node_id}> ").strip()
                if not cmd:
                    continue
                
                readline.add_history(cmd)
                
                if self._handle_special_commands(cmd):
                    continue
                
                # Отправка команды текущему узлу
                self.network.nodes[self.current_node_id].send_command(cmd)
                time.sleep(0.1)  # Даем время на обработку
                
            except KeyboardInterrupt:
                print("\nЗавершение работы...")
                break
            except Exception as e:
                print(f"Ошибка: {str(e)}")
        
        self._shutdown_network()

    def _handle_no_nodes_mode(self) -> None:
        """Обработка режима когда нет активных узлов"""
        cmd = input("> ").strip()
        if cmd.lower() in ("exit", "q"):
            raise KeyboardInterrupt()
        print("Нет активных узлов в сети. Используйте 'addnode' для создания узла.")

    def _handle_special_commands(self, cmd: str) -> bool:
        """Обработка специальных команд CLI"""
        cmd_lower = cmd.lower()
        
        if cmd_lower in ("exit", "q"):
            raise KeyboardInterrupt()
            
        parts = cmd.split()
        base_cmd = parts[0].lower()
        
        if base_cmd in self.network_commands:
            try:
                self.network_commands[base_cmd](*parts[1:])
            except Exception as e:
                print(f"Ошибка выполнения команды: {str(e)}")
            return True
            
        return False

    def _switch_node(self, *args):
        """Переключение на другой узел"""
        if not args:
            print("Доступные узлы:", list(self.network.nodes.keys()))
            try:
                new_id = int(input("Введите ID узла: "))
            except ValueError:
                print("Неверный ID узла")
                return
        else:
            try:
                new_id = int(args[0])
            except (ValueError, IndexError):
                print("Использование: switch [node_id]")
                return
        
        if new_id in self.network.nodes:
            self.current_node_id = new_id
            print(f"Переключено на узел {new_id}")
        else:
            print("Узел с таким ID не найден")

    def _kill_node(self, *args):
        """Удаление текущего узла"""
        return self.network.kill_node(int(args[0]))

    def _screenshot(self, *args):
        """Визуализация сети"""
        self.network.screenshot(self.current_node_id)

    def _record(self, *args):
        """Запись анимации сети"""
        try:
            fps = int(args[0]) if len(args) > 0 else 1
            duration = float(args[1]) if len(args) > 1 else 10
            self.recorder.start_recording(self.current_node_id, fps, duration)
        except (ValueError, IndexError):
            print("Использование: record [fps=1] [duration=10]")

    def _stop_recording(self, *args):
        """Остановка записи"""
        self.recorder.stop_recording()

    def _save_config(self, *args):
        """Сохранение конфигурации сети"""
        filename = args[0] if len(args) > 0 else None
        saved_path = self.network.save_network_config(filename)
        print(f"Конфигурация сохранена в: {saved_path}")

    def _add_node(self, *args):
        """Добавление нового узла"""
        try:
            x = float(args[0]) if len(args) > 0 else random.uniform(0, 100)
            y = float(args[1]) if len(args) > 1 else random.uniform(0, 100)
            node_id = max(self.network.nodes.keys(), default=0) + 1
            
            from src.p2p_node import P2PNode
            new_node = P2PNode(
                node_id=node_id,
                position=Position(x, y),
                network=self.network
            )
            new_node.start()
            self.network.add_node(new_node)
            
            print(f"Добавлен новый узел {node_id} на позиции ({x:.1f}, {y:.1f})")
            
            if self.current_node_id is None:
                self.current_node_id = node_id
                
        except Exception as e:
            print(f"Ошибка создания узла: {str(e)}")
            print("Использование: addnode [x] [y]")

    def _move_node(self, *args):
        """Перемещение узла в указанные координаты"""
        try:
            x = float(args[0])
            y = float(args[1])
            node_id = int(args[2]) if len(args) > 2 else self.current_node_id
            
            self.network.move_node(node_id, Position(x, y))
        except (ValueError, IndexError):
            print("Использование: moveto x y [node_id]")

    def _set_velocity(self, *args):
        """Установка скорости и направления движения узла"""
        try:
            velocity = float(args[0])
            direction = float(args[1])  # в градусах
            node_id = int(args[2]) if len(args) > 2 else self.current_node_id
            
            if node_id not in self.network.nodes:
                print("Узел с таким ID не найден")
                return
                
            node = self.network.nodes[node_id]
            node.state.velocity = velocity
            node.state.direction = math.radians(direction)
            print(f"Узел {node_id}: скорость {velocity:.1f} м/с, направление {direction:.1f}°")
            
        except (ValueError, IndexError):
            print("Использование: setvelocity speed direction_deg [node_id]")

    def _show_help(self, *args):
        """Показать справку по командам"""
        print("\n=== Доступные команды ===")
        print("\nСетевые команды:")
        print("  switch [id] - переключиться на узел")
        print("  kill - удалить текущий узел")
        print("  addnode [x] [y] - добавить новый узел")
        print("  moveto x y [id] - переместить узел в координаты")
        print("  setvelocity speed dir [id] - задать скорость узла")
        print("  screenshot - визуализировать сеть")
        print("  record [fps] [duration] - записать анимацию")
        print("  stop - остановить запись")
        print("  savecfg [filename] - сохранить конфигурацию")
        print("  help - показать эту справку")
        print("  exit/q - выход")
        from src.p2p_node import P2PNode
        P2PNode.cmd_help()

    def _shutdown_network(self) -> None:
        """Корректное завершение работы сети"""
        print("Остановка всех узлов...")
        for node in self.network.nodes.values():
            node.stop()
            node.join()
        print("Работа завершена.")

def interactive_control(network: 'NetworkSimulator'):
    """Интерактивное управление узлами сети"""
    CLICommandHandler(network).run()
