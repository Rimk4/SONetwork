import os
import subprocess
import sys

def frames_to_video_ffmpeg(input_dir, output_file, fps) -> None:
    """
    Использует ffmpeg для склейки кадров (требует установленного ffmpeg)
    
    :param input_dir: папка с кадрами
    :param output_file: имя выходного файла
    :param fps: кадры в секунду
    """
    try:
        cmd = [
            'ffmpeg',
            '-y',  # перезаписать если файл существует
            '-framerate', str(fps),
            '-i', os.path.join(input_dir, 'frame_%04d.png'),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',  # исправление для четных размеров
            output_file
        ]
        subprocess.run(cmd, check=True)
        print(f"Видео успешно создано: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при создании видео: {e}")
    except FileNotFoundError:
        print("FFmpeg не найден! Установите ffmpeg сначала.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Использование: python3 video_maker.py <input_dir> <output_file> <fps>")
        sys.exit(1)
        
    input_dir = sys.argv[1]
    output_file = sys.argv[2]
    fps = int(sys.argv[3])
    
    frames_to_video_ffmpeg(input_dir, output_file, fps)
