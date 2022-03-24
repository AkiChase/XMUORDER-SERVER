import os

from loguru import logger
from enum import Enum, unique


class Logger:
    """
    loguru二次封装，实现不同名称的logger对应不同的log文件
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
    def set_working_dir(cls, log_dir: str):
        """
        初始化，设置log文件夹路径
        :param log_dir:
        :return:
        """
        cls.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    @classmethod
    def __add(cls, _logger):
        cls.logger_dict[_logger.log_name] = _logger

    @classmethod
    def get_logger(cls, name: str):
        if name not in cls.logger_dict:
            raise Exception(f"the logger with name '{name}' doesn't exists")
        return cls.logger_dict[name]

    def __init__(self, log_name: str, level: Level = Level.SUCCESS):
        if log_name in Logger.logger_dict:
            raise Exception(f"the logger with name '{log_name}' already exists")

        self.log_name = log_name
        #   添加到Logger字典中
        Logger.__add(self)
        path = os.path.abspath(os.path.join(Logger.log_dir, f'{log_name}.log'))
        logger.add(path,
                   level=level.name,
                   format="[{time:YYYY-MM-DD HH:mm:ss}][{level}]: {message}",
                   encoding="utf-8",
                   rotation="1:00",
                   retention="30 days",
                   filter=lambda x: log_name == x['extra']['__log_name'])

    def debug(self, msg, *args, **kwargs):
        return logger.debug(msg, __log_name=self.log_name, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        return logger.info(msg, __log_name=self.log_name, *args, **kwargs)

    def success(self, msg, *args, **kwargs):
        return logger.success(msg, __log_name=self.log_name, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return logger.warning(msg, __log_name=self.log_name, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return logger.error(msg, __log_name=self.log_name, *args, **kwargs)
