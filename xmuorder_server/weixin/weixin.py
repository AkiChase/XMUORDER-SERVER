from datetime import datetime, timedelta

import requests

from .. import config
from ..common import XMUORDERException
from ..logger import Logger

logger: Logger


class WeiXin:
    app_id: str
    app_secret: str
    app_env: str

    # access_token过期时间  初始为1970年（保证过期）
    expiration: datetime = datetime.fromtimestamp(0)
    __access_token: str

    @classmethod
    def init(cls):
        #   获取默认日志
        global logger
        logger = Logger('微信模块')

        #   读取密钥环境等
        global_setting = config.GlobalSettings.get()
        cls.app_id = global_setting.app_id
        cls.app_secret = global_setting.app_secret
        cls.app_env = global_setting.app_env

    @classmethod
    def get_access_token(cls) -> str:
        """
        返回微信access_token，若过期则先更新
        """
        if datetime.now() > cls.expiration:
            url = 'https://api.weixin.qq.com/cgi-bin/token'
            data = {
                'appid': cls.app_id,
                'secret': cls.app_secret,
                'grant_type': 'client_credential'
            }
            res = requests.get(url=url, params=data)
            if res.status_code != 200:
                raise XMUORDERException('access_token获取失败')
            res_json = res.json()
            if 'access_token' in res_json and 'expires_in' in res_json:
                cls.__access_token = res_json['access_token']
                #   过期时间设置 预计超时时间-180s
                sec = int(res_json['expires_in']) - 180
                if sec <= 0:
                    sec = int(res_json['expires_in'])
                cls.expiration = datetime.now() + timedelta(seconds=sec)
            else:
                raise XMUORDERException('access_token获取失败')
            logger.debug('access_token已刷新')

        return cls.__access_token
