"""
安全相关
1. 简单代码验证
...
"""
from pydantic import BaseModel


class CodeVerifyModel(BaseModel):
    code: str


def code_verify(code: str) -> bool:
    """
    简单代码验证
    """
    return code == 'ff3710c390656e686b68d3694db30f5f'
