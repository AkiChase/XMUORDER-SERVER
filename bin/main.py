from fastapi import FastAPI

# 添加项目路径进入环境变量，防止找不到模块
import sys
import os

sys.path.append(os.path.split(os.path.abspath(os.path.dirname(__file__)))[0])

from xmuorder_server import config
from xmuorder_server.database import Mysql
from xmuorder_server.routers import sms

app = FastAPI()
#   短信相关 路由
app.include_router(sms.router, prefix="/sms")

config.GlobalSettings.init(_env_file='../.env')
settings = config.GlobalSettings.get()

Mysql.init(**settings.dict())


@app.get('/')
async def hello_world():
    return 'Hello world'


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=5716)
