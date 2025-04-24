# gui.py
import sys
import os
from typing import Optional
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QLineEdit, QPushButton, QTabWidget, QLabel,
                             QFileDialog, QListWidget, QSpinBox, QDoubleSpinBox)
from PySide2.QtCore import Qt, QThread, Signal, Slot
from PySide2.QtGui import QTextCursor, QPixmap
from PySide2.QtWidgets import QSizePolicy
from src.p2p_node import P2PNode
from src.models import Position

class NetworkThread(QThread):
    update_signal = Signal(str)

    def __init__(self, network, parent=None):
        super().__init__(parent)
        self.network = network
        self.running = True

    def run(self):
        while self.running:
            self.network.process_events()
            self.msleep(100)

    def stop(self):
        self.running = False
        self.wait()

class P2PGUI(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.current_node_id = next(iter(network.nodes)) if network.nodes else None
        self.init_ui()
        self.start_network_thread()

    def init_ui(self):
        self.setWindowTitle("P2P Network Simulator")
        self.setGeometry(100, 100, 900, 600)

        # Central Widget and Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel - Node Controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Node Management
        node_group = QWidget()
        node_layout = QVBoxLayout(node_group)
        
        self.node_list = QListWidget()
        self.update_node_list()
        node_layout.addWidget(QLabel("Nodes:"))
        node_layout.addWidget(self.node_list)
        self.node_list.currentItemChanged.connect(self.on_node_selected)

        node_layout.addWidget(QLabel("New Node Parameters:"))

        # Node ID
        self.node_id_spin = QSpinBox()
        self.node_id_spin.setRange(1, 1000000)
        self.node_id_spin.setValue(1)
        node_layout.addWidget(QLabel("Node ID:"))
        node_layout.addWidget(self.node_id_spin)

        # Velocity
        self.velocity_spin = QDoubleSpinBox()
        self.velocity_spin.setRange(0, 10000)
        self.velocity_spin.setDecimals(2)
        self.velocity_spin.setValue(0.0)
        node_layout.addWidget(QLabel("Velocity:"))
        node_layout.addWidget(self.velocity_spin)

        # Direction (градусы)
        self.direction_spin = QDoubleSpinBox()
        self.direction_spin.setRange(0, 360)
        self.direction_spin.setDecimals(2)
        self.direction_spin.setValue(0.0)
        node_layout.addWidget(QLabel("Direction (degrees):"))
        node_layout.addWidget(self.direction_spin)

        # Bitrate
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 1000000000)
        self.bitrate_spin.setValue(5000)
        node_layout.addWidget(QLabel("Bitrate:"))
        node_layout.addWidget(self.bitrate_spin)

        self.add_node_btn = QPushButton("Add Node")
        self.add_node_btn.clicked.connect(self.add_node)
        node_layout.addWidget(self.add_node_btn)

        self.kill_node_btn = QPushButton("Kill Node")
        self.kill_node_btn.clicked.connect(self.kill_node)
        node_layout.addWidget(self.kill_node_btn)

        left_layout.addWidget(node_group)

        # Node Position Control
        pos_group = QWidget()
        pos_layout = QVBoxLayout(pos_group)
        
        pos_layout.addWidget(QLabel("Position Control:"))
        
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-10000, 10000)
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-10000, 10000)
        
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(self.x_spin)
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(self.y_spin)

        self.move_btn = QPushButton("Move Node")
        self.move_btn.clicked.connect(self.move_node)
        pos_layout.addWidget(self.move_btn)

        left_layout.addWidget(pos_group)

        # Right Panel - Main Interface
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Tab Widget
        self.tabs = QTabWidget()
        
        # Console Tab
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.tabs.addTab(self.console, "Console")

        # Visualization Tab
        self.visualization = QLabel("Network Visualization")
        self.visualization.setAlignment(Qt.AlignCenter)
        self.tabs.addTab(self.visualization, "Visualization")
        self.visualization.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.visualization.setScaledContents(False)

        right_layout.addWidget(self.tabs)

        # Command Input
        self.command_input = QLineEdit()
        self.command_input.returnPressed.connect(self.execute_command)
        right_layout.addWidget(self.command_input)

        # Buttons
        btn_group = QWidget()
        btn_layout = QHBoxLayout(btn_group)
        
        self.visualize_btn = QPushButton("Visualize")
        self.visualize_btn.clicked.connect(self.visualize)
        btn_layout.addWidget(self.visualize_btn)

        self.record_btn = QPushButton("Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        btn_layout.addWidget(self.record_btn)

        self.save_btn = QPushButton("Save Config")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)

        right_layout.addWidget(btn_group)

        # Combine Layouts
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

    def start_network_thread(self):
        self.network_thread = NetworkThread(self.network)
        self.network_thread.update_signal.connect(self.update_console)
        self.network_thread.start()

    @Slot(str)
    def update_console(self, message):
        self.console.append(message)
        self.console.moveCursor(QTextCursor.End)

    def update_node_list(self):
        self.node_list.clear()
        for node_id in self.network.nodes:
            self.node_list.addItem(f"Node {node_id}")

    def on_node_selected(self, current, previous):
        if current is not None:
            # Предполагается, что текст элемента вида "Node <id>"
            text = current.text()
            try:
                node_id = int(text.split()[-1])
                self.current_node_id = node_id
                self.update_console(f"Выбран узел {node_id}")
            except ValueError:
                self.current_node_id = None
                self.update_console("Ошибка при определении ID узла")
        else:
            self.current_node_id = None
            self.update_console("Узел не выбран")

    def execute_command(self):
        cmd = self.command_input.text()
        self.command_input.clear()
        
        if not cmd:
            return
            
        if self.current_node_id:
            self.network.nodes[self.current_node_id].send_command(cmd)
        else:
            self.update_console("No active node selected")

    def add_node(self):
        self.update_console("Adding new node...")
        node_id = self.node_id_spin.value()
        velocity = self.velocity_spin.value()
        direction = self.direction_spin.value()
        bitrate = self.bitrate_spin.value()
        x = self.x_spin.value()
        y = self.y_spin.value()

        position = Position(x, y)

        new_node = P2PNode(
            node_id=node_id,
            position=position,
            network=self.network,
            bitrate=bitrate,
            velocity=velocity,
            direction=direction
        )

        try:
            self.network.add_node(new_node)
            self.update_console(f"Добавлен узел {node_id} с позицией ({x}, {y}), скоростью {velocity}, направлением {direction}, bitrate {bitrate}")
        except Exception as e:
            self.update_console(f"Ошибка добавления узла: {str(e)}")

        self.update_node_list()

    def kill_node(self):
        selected = self.node_list.currentItem()
        if selected:
            node_id = int(selected.text().split()[-1])
            self.update_console(f"Killing node {node_id}...")
            self.network.kill_node(node_id)
            self.update_node_list()

    def move_node(self):
        x = self.x_spin.value()
        y = self.y_spin.value()
        if self.current_node_id:
            # Implement node movement logic
            self.update_console(f"Moving node {self.current_node_id} to ({x}, {y})")

    def visualize(self):
        # Путь к изображению (замените на актуальный путь)
        image_path = self.network.visualize(self.current_node_id)

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self.update_console(f"Не удалось загрузить изображение: {image_path}")
                self.visualization.setText("Ошибка загрузки изображения")
            else:
                # Масштабируем изображение под размер QLabel, сохраняя пропорции
                scaled_pixmap = pixmap.scaled(
                    self.visualization.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.visualization.setPixmap(scaled_pixmap)
                self.update_console(f"Отображено изображение: {image_path}")
        else:
            self.update_console(f"Файл не найден: {image_path}")
            self.visualization.setText("Изображение не найдено")

    def toggle_recording(self):
        # Implement recording logic
        if self.record_btn.text() == "Start Recording":
            self.record_btn.setText("Stop Recording")
            self.update_console("Recording started...")
        else:
            self.record_btn.setText("Start Recording")
            self.update_console("Recording stopped")

    def save_config(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Config", "", "JSON Files (*.json)")
        if filepath:
            # Implement config saving logic
            self.update_console(f"Config saved to {filepath}")

    def closeEvent(self, event):
        self.network_thread.stop()
        super().closeEvent(event)

def start_gui(network):
    app = QApplication(sys.argv)
    gui = P2PGUI(network)
    gui.show()
    sys.exit(app.exec_())
