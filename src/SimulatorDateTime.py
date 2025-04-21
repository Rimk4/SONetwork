import datetime

class SimulatorDateTime(datetime.datetime):
    _start_time = None      # фиксированное стартовое время (datetime)
    _real_start = None      # момент запуска (реальное системное время)

    @classmethod
    def set_start_time(cls, start_time: datetime.datetime):
        cls._start_time = start_time
        cls._real_start = datetime.datetime.now()

    @classmethod
    def now(cls, tz=None):
        if cls._start_time is None or cls._real_start is None:
            # Если стартовое время не задано — возвращаем обычное текущее время
            return super().now(tz)
        elapsed = datetime.datetime.now(tz) - cls._real_start
        shifted = cls._start_time + elapsed
        if tz is not None:
            # Учитываем часовой пояс, если передан
            return shifted.astimezone(tz)
        return shifted
