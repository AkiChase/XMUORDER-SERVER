import requests

from ..common import XMUORDERException
from ..weixin.weixin import WeiXin


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
    def __operation_request(cls, base_url: str, collection_name: str, query: str):
        access_token = WeiXin.get_access_token()
        url = f'{base_url}?access_token={access_token}'
        post_data = {
            'env': WeiXin.app_env,
            'query': 'db.collection("{collection_name}").{query}'.format(
                collection_name=collection_name, query=query.replace('\n', ''))
        }
        return cls.__request(url=url, post_data=post_data)

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

        return cls.__request(url=url, post_data=post_data)

    @classmethod
    def count(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库计数 count()   query注意添加.count()
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseCount.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databasecount',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def query(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库查询   query中应使用limit()限制单次拉取的数量，默认会限制10条
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseQuery.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databasequery',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def aggregate(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库聚合操作    返回结果数量上限较高，注意在query中使用limit()
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseAggregate.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        :return:
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databaseaggregate',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def update(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库更新记录
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseUpdate.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        :return:
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databaseupdate',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def delete(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库删除记录
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseDelete.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        :return:
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databasedelete',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def add(cls, collection_name: str, query: str) -> dict:
        """
        微信云开发数据库插入记录
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseAdd.html
        :param collection_name: 集合名称
        :param query: 查询语句（不包括db.collection(xxx).）
        :return:
        """
        return cls.__operation_request(
            base_url='https://api.weixin.qq.com/tcb/databaseadd',
            collection_name=collection_name,
            query=query
        )

    @classmethod
    def collection_delete(cls, collection_name: str) -> dict:
        """
        微信云开发数据库删除集合
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseCollectionDelete.html
        :param collection_name: 集合名称
        :return:
        """
        access_token = WeiXin.get_access_token()
        url = f'https://api.weixin.qq.com/tcb/databasecollectiondelete?access_token={access_token}'
        post_data = {
            'env': WeiXin.app_env,
            'collection_name': collection_name
        }
        return cls.__request(url=url, post_data=post_data)

    @classmethod
    def collection_add(cls, collection_name: str) -> dict:
        """
        微信云开发数据库新增集合
        https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/database/databaseCollectionDelete.html
        :param collection_name: 集合名称
        :return:
        """
        access_token = WeiXin.get_access_token()
        url = f'https://api.weixin.qq.com/tcb/databasecollectionadd?access_token={access_token}'
        post_data = {
            'env': WeiXin.app_env,
            'collection_name': collection_name
        }
        return cls.__request(url=url, post_data=post_data)
