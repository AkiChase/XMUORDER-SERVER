from functools import lru_cache

from pydantic import BaseSettings

from xmuorder_server.common import ErrorInfo


class Settings(BaseSettings):
    database_host: str
    database_port: int = 3306
    database_user: str
    database_password: str
    database_name: str
    secret_id: str
    secret_key: str
    app_id: str
    app_secret: str
    app_env: str
    printer_user: str
    printer_key: str

    class Config:
        extra = "ignore"


class GlobalSettings:
    settings: Settings = None

    @classmethod
    def init(cls, _env_file):
        """
        初始化 读取配置文件
        """
        cls.settings = Settings(_env_file=_env_file)

    @classmethod
    def get(cls) -> Settings:
        """
        获取配置
        :return:
        """
        if cls.settings is None:
            raise Exception(ErrorInfo("settings not loaded"))
        return cls.settings
