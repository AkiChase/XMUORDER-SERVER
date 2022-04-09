from fastapi import APIRouter, HTTPException, Depends

from .. import dependencies
from ..logger import Logger
from ..weixin.database import UpdateDataBase

router = APIRouter()
logger: Logger


@router.on_event("startup")
async def __init():
    #   获取默认日志
    global logger
    logger = Logger('更新数据库模块')


@router.post("/canteen")
async def update_canteen_table(verify=Depends(dependencies.code_verify_aes_depend)):
    """
    通过微信数据库刷新同步canteen表
    """
    try:
        UpdateDataBase.update_canteen_table()
        logger.success(f'请求成功 -canteen 已刷新')
        return {
            'success': True,
            'msg': '刷新成功'
        }
    except Exception as e:
        logger.error(f'请求失败 -canteen 刷新失败 -{e}')
        raise HTTPException(status_code=400, detail='刷新失败')
