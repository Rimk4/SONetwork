# CLI Command Line Interface
import atexit
import os
import readline
import tempfile
import time
from src.FrameRecorder import FrameRecorder

def interactive_control(network: 'NetworkSimulator'):
    """Интерактивное управление узлами сети"""
    current_node_id = next(iter(network.nodes)) if network.nodes else None
    recorder = FrameRecorder(network)  # Добавляем рекордер

    # Создаем временный файл для истории текущей сессии
    temp_history = tempfile.NamedTemporaryFile(delete=False)
    temp_history.close()
    session_history_file = temp_history.name

    # Настраиваем readline для использования временного файла истории
    readline.read_history_file(session_history_file) if os.path.exists(session_history_file) else None

    def cleanup():
        """Очистка временных файлов при выходе"""
        try:
            os.unlink(session_history_file)
        except OSError:
            pass

    # Регистрируем очистку при выходе
    atexit.register(cleanup)
    atexit.register(readline.write_history_file, session_history_file)
    
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

            if cmd.lower() == "visualize":
                network.visualize(current_node_id)
                continue

            if cmd.lower().startswith("record"):
                parts = cmd.split()
                fps = int(parts[1]) if len(parts) > 1 else 1
                duration = float(parts[2]) if len(parts) > 2 else 10
                recorder.start_recording(current_node_id, fps, duration)
                continue

            if cmd.lower() == "stop":
                recorder.stop_recording()
                continue

            if cmd.lower().startswith("savecfg"):
                parts = cmd.split()
                filename = parts[1] if len(parts) > 1 else None
                if filename is None:
                    saved_path = network.save_network_config()
                else:
                    saved_path = network.save_network_config(filename)

                print(f"Конфигурация сохранена в: {saved_path}")
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
