from fastapi import HTTPException
from xmuorder_server import security


def code_verify_depend(code_verify: security.CodeVerifyModel):
    """
    验证code是否正确，不正确抛出400异常
    """
    if not security.code_verify(code_verify.code):
        raise HTTPException(status_code=400, detail="code invalid")
    return True


def code_verify_aes_depend(info: security.CodeVerifyModel):
    """
    验证aes加密的code是否正确，不正确抛出400异常
    """
    if not security.code_verify_aes(info.code, info.ts):
        raise HTTPException(status_code=400, detail="code invalid")
    return True
