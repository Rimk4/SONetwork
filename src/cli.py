import atexit
import os
import readline
import time
from src.constants import HISTORY_FILE

def interactive_control(network: 'NetworkSimulator'):
    """Интерактивное управление узлами сети"""
    current_node_id = next(iter(network.nodes)) if network.nodes else None

    # Load command history
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)

    # Save command history on exit
    atexit.register(readline.write_history_file, HISTORY_FILE)
    
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
