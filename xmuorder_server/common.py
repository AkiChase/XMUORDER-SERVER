from typing import Optional


class ErrorInfo:
    """
    自定义错误信息
    """
    msg: str
    success: int = 0
    errno: Optional[int]

    def __init__(self, msg: str, success: int = None, errno: int = None):
        self.msg = msg
        if success is not None:
            self.success = success
        if errno is not None:
            self.errno = errno


class SuccessInfo:
    """
    自定义成功信息
    """
    msg: str
    success: int = 1

    def __init__(self, msg: str, success: int = None):
        self.msg = msg
        if success is not None:
            self.success = success
