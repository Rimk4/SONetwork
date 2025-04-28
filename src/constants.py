# Константы из отчёта
R = 10000  # Радиус связи 10 км в метрах
V_MAX = 16.67  # Максимальная скорость 60 км/ч в м/с
BITRATE_RANGE = (32, 37000)  # Диапазон битрейтов (32 бит/с - 37 кбит/с)
SYN_SIZE = 16  # Размер SYN фрейма в байтах
ACK_SIZE = 8  # Размер ACK фрейма в байтах
DATA_FRAME_SIZE = 64  # Размер фрейма данных в байтах
T_SCAN = 5  # Интервал сканирования в секундах
T_TIMEOUT = 5  # Таймаут соединения в секундах

# Папки и файлы
OUT_DIR = "out"
LOG_DIR = f"{OUT_DIR}/logs"
FRAMES_DIR = f"{OUT_DIR}/network_frames"
CONFIGS_DIR = f"{OUT_DIR}/saved_networks"
