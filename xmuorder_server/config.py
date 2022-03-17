from pydantic import BaseSettings


class Settings(BaseSettings):
    host: str
    port: int = 3306
    user: str
    password: str
    database_name: str

    class Config:
        extra = "ignore"
