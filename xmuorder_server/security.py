"""
安全相关
1. 简单代码验证
2. 加密解密
...
"""
import base64
from typing import Optional

from Crypto.Cipher import AES as _AES

from pydantic import BaseModel


class CodeVerifyModel(BaseModel):
    code: str
    ts: Optional[str] = None


def code_verify(code: str) -> bool:
    """
    简单代码验证
    """
    return code == 'ff3710c390656e686b68d3694db30f5f'


def code_verify_aes(code: str, ts: str) -> bool:
    """
    时间戳 aes验证
    :param code: 待验证字符串
    :param ts: 时间戳
    :return: bool
    """
    try:
        key = 'ord' + ts[0:11] + 'er_'
        iv = 're_' + ts[0:11] + 'dro'
        return AES.encrypt_aes(key=key, iv=iv, src=ts) == code
    except:
        return False


class AES:
    """
    AES 加密解密
    """

    @staticmethod
    def encrypt_aes(key: str, iv: str, src) -> str:
        """
        aes加密 输出base64
        :param key: 16 128位
        :param iv:  16 128位
        :param src: 待加密字符串
        :return: 加密字符串
        """
        padding_str = AES._pad(src)
        cipher = _AES.new(key.encode('utf-8'), _AES.MODE_CBC, iv.encode('utf-8'))
        dest = base64.b64encode(cipher.encrypt(padding_str))
        return dest.decode('utf-8')

    @staticmethod
    def decrypt_aes(key: str, iv: str, en_src: str) -> str:
        """
        aes解密
        :param key: 16 128位
        :param iv:  16 128位
        :param en_src: 加密字符串
        :return: 解密字符串
        :return:
        """
        en_data = base64.b64decode(en_src)
        cipher = _AES.new(key.encode('utf-8'), _AES.MODE_CBC, iv.encode('utf-8'))
        dest_data = AES._un_pad(cipher.decrypt(en_data))
        dest = dest_data.decode(encoding="utf-8")
        return dest

    @staticmethod
    def _pad(s):
        bs = _AES.block_size
        s = s.encode("utf-8")
        return s + (bs - len(s) % bs) * chr(bs - len(s) % bs).encode("utf-8")

    @staticmethod
    def _un_pad(s):
        return s[:-ord(s[len(s) - 1:])]
