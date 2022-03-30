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

    def to_dict(self):
        out = {'msg': self.msg, 'success': self.success}
        if hasattr(self, 'errno'):
            out['errno'] = self.errno
        if hasattr(self, 'data'):
            out['data'] = self.data
        return out


class SuccessInfo:
    """
    自定义成功信息
    """
    msg: str
    success: int
    data: Optional[dict]

    def __init__(self, msg: str, success: int = 1, data: dict = None):
        self.msg = msg
        self.success = success
        if data is not None:
            self.data = data

    def to_dict(self) -> dict:
        out = {'msg': self.msg, 'success': self.success}
        if hasattr(self, 'data'):
            out['data'] = self.data
        return out


class XMUORDERException(Exception):
    """
    自定义异常
    """

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class WithMsgException(Exception):
    """
    面向api接口附加错误消息的自定义类型
    """

    def __init__(self, msg: str, data=None):
        self.msg = msg
        self.data = data
