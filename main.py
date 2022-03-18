from fastapi import FastAPI

from xmuorder_server import config, database
from xmuorder_server.routers import sms

app = FastAPI()
app.include_router(sms.router, prefix="/sms")

config.GlobalSettings.init(_env_file='.env')
settings = config.GlobalSettings.get()

db = database.Mysql(**settings.dict())


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/")
async def root():
    return {"message": "Hello World"}


if __name__ == "__main__":
    import uvicorn

    # 使用命令行启动main.py，使用CTRL+C退出，保证数据库连接池正常关闭
    uvicorn.run(app, host=settings.server_host, port=settings.server_port)
