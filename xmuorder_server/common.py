from typing import Optional


class ErrorInfo:
    """
    自定义错误信息
    """
    msg: str
    success: int = 0
    errno: Optional[int]
    data: Optional[dict]

    def __init__(self, msg: str, success: int = None, errno: int = None, data: dict = None):
        self.msg = msg
        if success is not None:
            self.success = success
        if errno is not None:
            self.errno = errno
        if data is not None:
            self.data = data


class SuccessInfo:
    """
    自定义成功信息
    """
    msg: str
    success: int = 1
    data: Optional[dict]

    def __init__(self, msg: str, success: int = None, data: dict = None):
        self.msg = msg
        if success is not None:
            self.success = success
        if data is not None:
            self.data = data
