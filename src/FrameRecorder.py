import os
import time
from threading import Thread
from src.constants import FRAMES_DIR

class FrameRecorder:
    def __init__(self, network) -> None:
        self.network = network
        self.recording = False
        self.fps = 1
        self.duration = 0
        self.observer_id = None
        self.thread = None
        self.output_dir = ""

    def start_recording(self, observer_id=None, fps=1, duration=10) -> None:
        """Запуск записи последовательности кадров в фоновом режиме"""
        if self.recording:
            print("Запись уже идет!")
            return

        self.observer_id = observer_id
        self.fps = fps
        self.duration = duration
        timestamp = self.network.start_time.strftime("%Y%m%d_%H%M%S")
        self.output_dir = f"{FRAMES_DIR}/network_frames_{timestamp}/recorded_{time.time()}"
        os.makedirs(self.output_dir, exist_ok=True)

        self.recording = True
        self.thread = Thread(target=self._record_frames, daemon=True)
        self.thread.start()
        print(f"Начата запись {duration} секунд с частотой {fps} FPS в папку '{self.output_dir}'")

    def create_video_command_file(self) -> None:
        """Создает файл с командой для генерации видео"""
        command_file = os.path.join(self.output_dir, "create_video.sh")
        
        with open(command_file, 'w') as f:
            f.write(f"#!/bin/bash\n")
            f.write(f"python3 src/video_maker.py '{self.output_dir}' '{self.output_dir}/output.mp4' {self.fps}\n")
        
        # Делаем файл исполняемым (Unix-like системы)
        os.chmod(command_file, 0o755)
        print(f"Командный файл создан: {command_file}")
        print(f"Нажать ↵")

    def _record_frames(self) -> None:
        """Фоновый процесс записи кадров"""
        start_time = time.time()
        frame_count = 0

        while self.recording and (time.time() - start_time) < self.duration:
            frame_time = time.time()
            frame_path = os.path.join(self.output_dir, f"frame_{frame_count:04d}.png")
            self.network.visualize(observer_id=self.observer_id, frame_name=frame_path)

            frame_count += 1
            sleep_time = (1/self.fps) - (time.time() - frame_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.recording = False
        print(f"Запись завершена. Сохранено {frame_count} кадров")
        self.create_video_command_file()

    def stop_recording(self) -> None:
        """Остановка записи"""
        if self.recording:
            self.recording = False
            print("Запись остановлена")
        else:
            print("Нет активной записи")
        if self.thread is not None and self.thread.is_alive():
            print("here")
            self.thread.join()
