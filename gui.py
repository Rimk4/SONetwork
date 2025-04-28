# gui.py
from queue import Empty, Queue
import threading
import time
import dearpygui.dearpygui as dpg
import os
from src.p2p_node import P2PNode
from src.models import Position
import numpy as np
class NetworkThread:
    def __init__(self, network):
        self.network = network

    def process_events(self):
        self.network.process_events()

class LogWatcher:
    def __init__(self, gui):
        self.gui = gui
        self.log_queue = Queue()
        self.stop_event = threading.Event()
        self.watcher_thread = threading.Thread(target=self.watch_logs, daemon=True)
        self.watcher_thread.start()

    def watch_logs(self):
        last_position = {}
        while not self.stop_event.is_set():
            if self.gui.current_node_id:
                node_id = self.gui.current_node_id
                log_file = f"out/logs/node_{node_id}.log"
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r') as f:
                            # Определяем текущий размер файла
                            f.seek(0, 2)
                            file_size = f.tell()
                            
                            # Если файл уменьшился (был перезаписан), сбрасываем позицию
                            if node_id in last_position and last_position[node_id] > file_size:
                                last_position[node_id] = 0
                            
                            # Переходим на последнюю известную позицию
                            f.seek(last_position.get(node_id, 0))
                            
                            # Читаем новые строки
                            new_lines = f.readlines()
                            if new_lines:
                                last_position[node_id] = f.tell()
                                # Отправляем последние 10 строк в очередь
                                self.log_queue.put((node_id, new_lines[-10:]))
                    except Exception as e:
                        print(f"Error reading log file: {e}")
            time.sleep(0.5)

    def stop(self):
        self.stop_event.set()
        self.watcher_thread.join()

class P2PGUI:
    def __init__(self, network):
        self.network = network
        self.current_node_id = next(iter(network.nodes)) if network.nodes else None
        self.console_text = ""
        self.recording = False
        self.language = "en"  # По умолчанию английский
        self.last_update_time = 0  # Время последнего обновления изображения
        self.last_log_update_time = 0  # Время последнего обновления логов
        self.log_watcher = LogWatcher(self)
        self.current_log_content = ""
        self.texts = {
            "en": {
                "window_title": "P2P Network Simulator",
                "nodes": "Nodes:",
                "new_node_params": "New Node Parameters:",
                "node_id": "Node ID",
                "velocity": "Velocity [m/s]",
                "direction": "Direction [°]",
                "bitrate": "Bitrate",
                "add_node": "Add Node",
                "kill_node": "Kill Node",
                "position_control": "Position Control:",
                "x_pos": "X",
                "y_pos": "Y",
                "move_node": "Move Node",
                "console": "Console",
                "topology": "Topology",
                "network_topology": "Network Topology",
                "command_input": "Command Input",
                "screenshot": "Screenshot",
                "start_recording": "Start Recording",
                "stop_recording": "Stop Recording",
                "save_config": "Save Config",
                "node_selected": "Selected node {}",
                "node_selection_error": "Error determining node ID",
                "no_node_selected": "No node selected",
                "no_active_node": "No active node selected",
                "adding_node": "Adding new node...",
                "node_added": "Added node {} with position ({}, {}), velocity {}, direction {}, bitrate {}",
                "node_add_error": "Error adding node: {}",
                "killing_node": "Killing node {}...",
                "moving_node": "Moving node...",
                "node_moved": "Moved node {} to ({}, {})",
                "image_displayed": "Displayed image: {}",
                "image_load_error": "Failed to load or display image: {}",
                "image_error": "Image loading error",
                "file_not_found": "File not found: {}",
                "image_not_found": "Image not found",
                "recording_started": "Recording started...",
                "recording_stopped": "Recording stopped",
                "config_saved": "Configuration saved to: {}",
                "language": "Language",
                "node_logs": "Node Logs",
                "no_log_file": "No log file for node {}",
                "log_update_error": "Error updating logs: {}",
                "decay_rate": "Decay Rate",
                "set_decay_rate": "Set Decay Rate",
                "destruct_on": "Errors On",
                "destruct_off": "Errors Off",
            },
            "ru": {
                "window_title": "P2P Сетевой Симулятор",
                "nodes": "Узлы:",
                "new_node_params": "Параметры нового узла:",
                "node_id": "ID узла",
                "velocity": "Скорость [м/с]",
                "direction": "Направление [°]",
                "bitrate": "Битрейт",
                "add_node": "Добавить узел",
                "kill_node": "Удалить узел",
                "position_control": "Управление позицией:",
                "x_pos": "X",
                "y_pos": "Y",
                "move_node": "Переместить узел",
                "console": "Консоль",
                "topology": "Визуализация",
                "network_topology": "Визуализация сети",
                "command_input": "Ввод команды",
                "screenshot": "Скриншот",
                "start_recording": "Начать запись",
                "stop_recording": "Остановить запись",
                "save_config": "Сохранить конфигурацию",
                "node_selected": "Выбран узел {}",
                "node_selection_error": "Ошибка при определении ID узла",
                "no_node_selected": "Узел не выбран",
                "no_active_node": "Не выбран активный узел",
                "adding_node": "Добавление нового узла...",
                "node_added": "Добавлен узел {} с позицией ({}, {}), скоростью {}, направлением {}, битрейтом {}",
                "node_add_error": "Ошибка добавления узла: {}",
                "killing_node": "Удаление узла {}...",
                "moving_node": "Перемещение узла...",
                "node_moved": "Узел {} перемещен в ({}, {})",
                "image_displayed": "Отображено изображение: {}",
                "image_load_error": "Не удалось загрузить или отобразить изображение: {}",
                "image_error": "Ошибка загрузки изображения",
                "file_not_found": "Файл не найден: {}",
                "image_not_found": "Изображение не найдено",
                "recording_started": "Запись начата...",
                "recording_stopped": "Запись остановлена",
                "config_saved": "Конфигурация сохранена в: {}",
                "language": "Язык",
                "node_logs": "Логи узла",
                "no_log_file": "Нет файла лога для узла {}",
                "log_update_error": "Ошибка обновления логов: {}",
                "decay_rate": "Коэффициент затухания",
                "set_decay_rate": "Установить коэффициент",
                "destruct_on": "Включить помехи",
                "destruct_off": "Отключить помехи",
            }
        }
        
        self.network_thread = NetworkThread(self.network)
        self.init_ui()

    def t(self, key, *args):
        """Получить переведенный текст с форматированием"""
        return self.texts[self.language][key].format(*args)

    def init_ui(self):
        dpg.create_context()

        with dpg.font_registry():
            with dpg.font("resources/notomono-regular.ttf", 16, default_font=True, tag="Default font") as f:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
        dpg.bind_font("Default font")

        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (60, 60, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 60, 60, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 80, 80, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 100, 100, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
        dpg.bind_theme(global_theme)

        # Инициализация пустой текстуры
        self.texture_data = np.ones((500, 400, 4), dtype=np.float32)
        with dpg.texture_registry():
                dpg.add_raw_texture(
                    500,
                    400,
                    self.texture_data,
                    format=dpg.mvFormat_Float_rgba,
                    tag="topology_texture",
                )

        with dpg.window(label=self.t("window_title"), width=900, height=600) as main_window:
            with dpg.child_window(width=350, height=-1, pos=[0, 20]):
                dpg.add_text(self.t("nodes"))
                dpg.add_listbox(
                    items=[f"Node {node_id}" for node_id in self.network.nodes],
                    width=200,
                    callback=self.on_node_selected,
                    tag="node_list",
                )
                dpg.add_text(self.t("new_node_params"))
                dpg.add_input_int(label=self.t("node_id"), width=200, default_value=1, tag="node_id")
                dpg.add_input_float(
                    label=self.t("velocity"), width=200, default_value=0.0, tag="velocity", format="%.2f"
                )
                dpg.add_input_float(
                    label=self.t("direction"), width=200, default_value=0.0, tag="direction", format="%.2f"
                )
                dpg.add_input_int(label=self.t("bitrate"), width=200, default_value=5000, tag="bitrate")
                dpg.add_button(label=self.t("add_node"), callback=self.add_node, tag="add_node")
                dpg.add_button(label=self.t("kill_node"), callback=self.kill_node, tag="kill_node")

                dpg.add_text(self.t("position_control"))
                dpg.add_input_float(label=self.t("x_pos"), width=200, default_value=0.0, tag="x_pos")
                dpg.add_input_float(label=self.t("y_pos"), width=200, default_value=0.0, tag="y_pos")
                dpg.add_button(label=self.t("move_node"), callback=self.move_node, tag="move_node")
                
                # Добавляем поле для decay_rate после других параметров
                dpg.add_input_float(
                    label="Decay Rate",
                    width=200,
                    default_value=0.3,
                    format="%.2f",
                    min_value=0.0,
                    max_value=1.0,
                    tag="decay_rate"
                )
                
                # Добавляем кнопку для применения значения
                dpg.add_button(
                    label=self.t("set_decay_rate"),
                    callback=self.set_decay_rate,
                    tag="set_decay_rate"
                )

                dpg.add_radio_button(
                    items=[self.t("destruct_on"), self.t("destruct_off")],
                    callback=self.choose_errors_on_off,
                    tag="destruction_selector",
                    default_value=self.t("destruct_off")
                )

                # Добавляем переключатель языка
                dpg.add_text(self.t("language"))
                dpg.add_radio_button(
                    items=["English", "Русский"],
                    callback=self.change_language,
                    tag="language_selector",
                    default_value="English" if self.language == "en" else "Русский"
                )

            with dpg.child_window(width=-1, height=-1, pos=[350, 20]):
                with dpg.tab_bar():
                    with dpg.tab(label=self.t("console")):
                        dpg.add_input_text(
                            multiline=True,
                            readonly=True,
                            width=-1,
                            height=400,
                            tag="console",
                        )

                    with dpg.tab(label=self.t("topology")):
                        dpg.add_image(
                            "topology_texture", 
                            width=500,
                            height=400,
                            tag="network_image"
                        )
                        dpg.add_text(self.t("network_topology"), tag="topology_text")

                    with dpg.tab(label=self.t("node_logs")):
                        dpg.add_input_text(
                            multiline=True,
                            readonly=True,
                            width=-1,
                            height=400,
                            tag="node_logs_display",
                        )

                dpg.add_input_text(
                    label=self.t("command_input"), on_enter=True, callback=self.execute_command, tag="command_input"
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(label=self.t("screenshot"), callback=self.screenshot, tag="screenshot")
                    dpg.add_button(
                        label=self.t("start_recording"),
                        callback=self.toggle_recording,
                        tag="record_button"
                    )
                    dpg.add_button(label=self.t("save_config"), callback=self.save_config, tag="save_config")

    def change_language(self, sender, data):
        self.language = "en" if data == "English" else "ru"
        self.update_ui_language()
    
    def choose_errors_on_off(self, sender, data):
        self.network.set_trans_probability_flag(True if data == self.t("destruct_on") else False)

    def update_ui_language(self):
        """Обновление всех текстовых элементов интерфейса"""
        dpg.set_viewport_title(self.t("window_title"))
        
        # Обновляем тексты в левой панели
        dpg.set_item_label("node_list", self.t("nodes"))
        dpg.configure_item("node_id", label=self.t("node_id"))
        dpg.configure_item("velocity", label=self.t("velocity"))
        dpg.configure_item("direction", label=self.t("direction"))
        dpg.configure_item("bitrate", label=self.t("bitrate"))
        dpg.configure_item("add_node", label=self.t("add_node"))
        dpg.configure_item("kill_node", label=self.t("kill_node"))
        dpg.configure_item("x_pos", label=self.t("x_pos"))
        dpg.configure_item("y_pos", label=self.t("y_pos"))
        dpg.configure_item("move_node", label=self.t("move_node"))
        dpg.configure_item("decay_rate", label=self.t("decay_rate"))
        dpg.configure_item("set_decay_rate", label=self.t("set_decay_rate"))
        
        # Обновляем тексты в правой панели
        dpg.set_item_label("console", self.t("console"))
        dpg.set_item_label("network_image", self.t("topology"))
        dpg.set_item_label("topology_text", self.t("network_topology"))
        dpg.configure_item("command_input", label=self.t("command_input"))
        dpg.configure_item("screenshot", label=self.t("screenshot"))
        dpg.configure_item("record_button", label=self.t("stop_recording" if self.recording else "start_recording"))
        dpg.configure_item("save_config", label=self.t("save_config"))
        
        # Обновляем переключатель языка
        dpg.configure_item("language_selector", items=["English", "Русский"], default_value="English" if self.language == "en" else "Русский")

    def set_decay_rate(self):
        decay_rate = dpg.get_value("decay_rate")
        if 0 <= decay_rate <= 1:
            self.network.set_decay_rate(decay_rate)
            self.update_console(f"Decay rate set to {decay_rate}")
        else:
            self.update_console("Decay rate must be between 0 and 1")

    def update_console(self, message):
        self.console_text += message + "\n"
        dpg.set_value("console", self.console_text)

    def update_log_display(self):
        try:
            # Проверяем очередь на наличие новых логов
            while True:
                node_id, lines = self.log_watcher.log_queue.get_nowait()
                if node_id == self.current_node_id:
                    self.current_log_content = "".join(lines)
                    dpg.set_value("node_logs_display", self.current_log_content)
        except Empty:
            pass

    def run(self):
        dpg.create_viewport(title=self.t("window_title"), width=900, height=600)
        dpg.setup_dearpygui()
        dpg.show_viewport()

        while dpg.is_dearpygui_running():
            current_time = time.time()
            
            # Обновляем изображение каждую секунду
            if current_time - self.last_update_time >= 1.0:
                self.screenshot()
                self.last_update_time = current_time
            
            # Обновляем логи каждые 0.5 секунды
            if current_time - self.last_log_update_time >= 0.5:
                self.update_log_display()
                self.last_log_update_time = current_time
                
            self.network_thread.process_events()
            dpg.render_dearpygui_frame()

        self.log_watcher.stop()
        dpg.destroy_context()

    def update_node_list(self):
        nodes = [f"Node {node_id}" for node_id in self.network.nodes]
        dpg.configure_item("node_list", items=nodes)

    def on_node_selected(self, sender, data):
        selected_node = dpg.get_value("node_list")
        if selected_node:
            try:
                node_id = int(selected_node.split()[-1])
                self.current_node_id = node_id
                self.update_console(self.t("node_selected", node_id))
            except ValueError:
                self.current_node_id = None
                self.update_console(self.t("node_selection_error"))
        else:
            self.current_node_id = None
            self.update_console(self.t("no_node_selected"))

    def execute_command(self):
        cmd = dpg.get_value("command_input")
        dpg.set_value("command_input", "")
        if not cmd:
            return

        if self.current_node_id:
            self.network.nodes[self.current_node_id].send_command(cmd)
        else:
            self.update_console(self.t("no_active_node"))

    def add_node(self):
        self.update_console(self.t("adding_node"))
        node_id = dpg.get_value("node_id")
        velocity = dpg.get_value("velocity")
        direction = dpg.get_value("direction")
        bitrate = dpg.get_value("bitrate")
        x = dpg.get_value("x_pos")
        y = dpg.get_value("y_pos")
        position = Position(x, y)

        new_node = P2PNode(
            node_id=node_id,
            position=position,
            network=self.network,
            bitrate=bitrate,
            velocity=velocity,
            direction=direction,
        )

        try:
            self.network.add_node(new_node)
            new_node.start()
            self.update_console(self.t("node_added", node_id, x, y, velocity, direction, bitrate))
        except Exception as e:
            self.update_console(self.t("node_add_error", str(e)))

        self.update_node_list()

    def kill_node(self):
        selected_node = dpg.get_value("node_list")
        if selected_node:
            node_id = int(selected_node.split()[-1])
            self.update_console(self.t("killing_node", node_id))
            self.network.kill_node(node_id)
            self.update_node_list()

    def move_node(self):
        x = dpg.get_value("x_pos")
        y = dpg.get_value("y_pos")
        if self.current_node_id:
            self.update_console(self.t("moving_node"))
            self.network.move_node(self.current_node_id, Position(x, y))
            self.update_console(self.t("node_moved", self.current_node_id, x, y))

    def screenshot(self):
        image_path = self.network.screenshot(self.current_node_id)
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image
                
                # Загружаем и подготавливаем изображение
                img = Image.open(image_path).resize((500, 400))  # Обратите внимание на размеры (width, height)
                # img = img.transpose(Image.FLIP_TOP_BOTTOM)  # Переворачиваем по вертикали
                img = img.convert("RGBA")
                
                # Конвертируем в numpy массив и нормализуем
                img_array = np.array(img, dtype=np.float32) / 255.0
                
                # Обновляем текстуру
                dpg.set_value("topology_texture", img_array)
                
                # Обновляем отображение (размеры должны соответствовать размерам текстуры)
                dpg.configure_item("network_image", width=500, height=400)
                self.update_console(self.t("image_displayed", image_path))
            except Exception as e:
                self.update_console(self.t("image_load_error", str(e)))
        else:
            self.update_console(self.t("file_not_found", image_path if image_path else "None"))

    def toggle_recording(self):
        if not self.recording:
            self.update_console(self.t("recording_started"))
        else:
            self.update_console(self.t("recording_stopped"))
        self.recording = not self.recording
        dpg.set_item_label("record_button", self.t("stop_recording" if self.recording else "start_recording"))

    def save_config(self):
        saved_path = self.network.save_network_config()
        self.update_console(self.t("config_saved", saved_path))

def start_gui(network):
    gui = P2PGUI(network)
    gui.run()
