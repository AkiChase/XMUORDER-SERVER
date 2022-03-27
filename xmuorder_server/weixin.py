from datetime import datetime, timedelta

import requests

from .common import XMUORDERException
from .config import GlobalSettings
from .logger import Logger

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
        global_setting = GlobalSettings.get()
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


class Database:
    """
    数据库相关操作封装
    """

    @staticmethod
    def __request(url: str, post_data: dict, **kwargs) -> dict:
        res = requests.post(url=url, json=post_data, **kwargs)
        if res.status_code != 200:
            raise XMUORDERException('requests failed')
        res_json = res.json()
        if res_json['errcode'] != 0:
            raise XMUORDERException(res_json['errmsg'])
        return res_json

    @classmethod
    def collection_get(cls, limit: int = 10, offset: int = 0):
        """
        获取特定云环境下集合信息
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseCollectionGet.html
        :return:
        """
        access_token = WeiXin.get_access_token()
        url = f'https://api.weixin.qq.com/tcb/databasecollectionget?access_token={access_token}'
        post_data = {
            'env': WeiXin.app_env,
            'limit': limit,
            'offset': offset
        }

        res_json = cls.__request(url=url, post_data=post_data)

        return {
            'collections': res_json['collections'],
            'pager': res_json['pager']
        }

    @classmethod
    def aggregate(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库聚合操作    返回结果数量上限较高，注意使用limit
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseAggregate.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).aggregate().）
        :return:
        """
        access_token = WeiXin.get_access_token()
        url = f'https://api.weixin.qq.com/tcb/databaseaggregate?access_token={access_token}'
        post_data = {
            'env': WeiXin.app_env,
            'query': 'db.collection("{collection_name}").aggregate().{query}'.format(
                collection_name=collection_name, query=query.replace('\n', ''))
        }

        res_json = cls.__request(url=url, post_data=post_data)
        return res_json['data']
