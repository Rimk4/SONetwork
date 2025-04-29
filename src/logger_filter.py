from enum import Enum
import logging


class LogModule(Enum):
    ROUTING = "ROUT"
    NETWORK = "NET"
    COM = "COM"

class ModuleFilter(logging.Filter):
    """Фильтр логгирования по модулю"""
    
    def __init__(self, module: Enum):
        super().__init__()
        self.module = module
        
    def filter(self, record: logging.LogRecord) -> bool:
        # Проверяем, содержит ли сообщение название модуля
        return str(self.module.name) in record.getMessage()
