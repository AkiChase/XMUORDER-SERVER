from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .. import dependencies, security
from ..common import SuccessInfo, ErrorInfo
from ..security import AES

router = APIRouter()


class BindModel(BaseModel):
    """
    登录信息模版
    """
    id: str
    uid: str
    pw: str
    ts: str


class LoginModel(BaseModel):
    """
    登录信息模版
    """
    uid: str
    ts: str


@router.post("/bind")
async def xmu_bind(data: BindModel, verify=Depends(dependencies.code_verify_depend)):
    key = 'ord' + data.ts[0:11] + 'er_'
    iv = 're_' + data.ts[0:11] + 'dro'
    user_id = AES.encrypt_aes(key, iv, src=data.id)
    password = AES.encrypt_aes(key, iv, src=data.pw)
    openid = AES.encrypt_aes(key, iv, src=data.uid)

    # 通过账号密码爬取获取需要的信息
    # 储存需要的信息到mysql（以openid为主键）

    return SuccessInfo('bind success', data={
        #   需要返回的信息 dict
    })

    raise HTTPException(status_code=400, detail=ErrorInfo('bind failed'))


@router.post("/login")
async def xmu_login(data: LoginModel, verify=Depends(dependencies.code_verify_depend)):
    key = 'ord' + data.ts[0:11] + 'er_'
    iv = 're_' + data.ts[0:11] + 'dro'
    openid = AES.encrypt_aes(key, iv, src=data.uid)

    return SuccessInfo('login success', data={
        #   需要返回的信息 dict
    })

    raise HTTPException(status_code=400, detail=ErrorInfo('login failed'))
