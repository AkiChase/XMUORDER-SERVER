import os

from loguru import logger
from enum import Enum, unique


class Logger:
    """
    loguru二次封装，实现不同名称的logger对应不同的消息前缀
    """
    log_dir: str
    logger_dict: dict = {}

    @unique
    class Level(Enum):
        DEBUG = 1
        INFO = 2
        SUCCESS = 3
        WARNING = 4
        ERROR = 5

    @classmethod
    def init(cls, log_path: str, level: Level = Level.SUCCESS):
        """
        初始化，设置log路径
        """
        log_dir = os.path.dirname(log_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logger.add(log_path,
                   level=level.name,
                   format="[{time:YYYY-MM-DD HH:mm:ss}][{level}]: {message}",
                   encoding="utf-8",
                   rotation="01:00",
                   retention="30 days")

    @classmethod
    def __add(cls, _logger):
        cls.logger_dict[_logger.log_name] = _logger

    @classmethod
    def get_logger(cls, name: str):
        if name not in cls.logger_dict:
            raise Exception(f"the logger with name '{name}' doesn't exists")
        return cls.logger_dict[name]

    def __init__(self, log_name: str):
        if log_name in Logger.logger_dict:
            raise Exception(f"the logger with name '{log_name}' already exists")

        self.log_name = log_name
        #   添加到Logger字典中
        Logger.__add(self)

    def debug(self, msg, *args, **kwargs):
        return logger.debug(f'[{self.log_name}]\t{msg}', __log_name=self.log_name, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        return logger.info(f'[{self.log_name}]\t{msg}', __log_name=self.log_name, *args, **kwargs)

    def success(self, msg, *args, **kwargs):
        return logger.success(f'[{self.log_name}]\t{msg}', __log_name=self.log_name, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return logger.warning(f'[{self.log_name}]\t{msg}', __log_name=self.log_name, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return logger.error(f'[{self.log_name}]\t{msg}', __log_name=self.log_name, *args, **kwargs)
