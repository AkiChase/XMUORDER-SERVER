from fastapi import FastAPI

# 添加项目路径进入环境变量，防止找不到模块
import sys
import os

sys.path.append(os.path.split(os.path.abspath(os.path.dirname(__file__)))[0])

from xmuorder_server import config
from xmuorder_server.database import Mysql
from xmuorder_server.routers import sms, xmu
from xmuorder_server.logger import Logger
from xmuorder_server.scheduler import Scheduler
from xmuorder_server.weixin.weixin import WeiXin

app = FastAPI()


@app.on_event("startup")
async def __init():
    #   logger初始化
    Logger.init(os.path.abspath(os.path.join(__file__, '../../log/日志.log')))

    #   短信相关 路由
    app.include_router(sms.router, prefix="/sms")
    #   xmu绑定 路由
    app.include_router(xmu.router, prefix="/xmu")

    #   配置文件读取
    config.GlobalSettings.init(_env_file='../.env')
    settings = config.GlobalSettings.get()

    #   Mysql连接
    Mysql.init(**settings.dict())

    #   微信模块初始化
    WeiXin.init()

    #   scheduler初始化, router模块需要的任务在模块__init中添加
    Scheduler.init()


@app.get('/')
async def hello_world():
    return 'hello world'


if __name__ == "__main__":
    import uvicorn

    # noinspection PyTypeChecker
    uvicorn.run(app, host='127.0.0.1', port=5716)
