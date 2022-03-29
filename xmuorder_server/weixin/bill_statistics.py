from xmuorder_server.logger import Logger
from xmuorder_server.weixin.database import Database
from xmuorder_server.common import XMUORDERException
from decimal import *
import json

logger:Logger
class bill_stat:
    @classmethod
    def get_order_data(cls, endDate:str):
        '''
        获取前端传来的数据结果
        '''
        query = f'''
        aggregate().match({{'orderInfo.orderState': 'SUCCESS', 'payInfo.tradeState': 'SUCCESS',
        'orderInfo.timeInfo.confirmTime':_.gte('{endDate+'0000'}'),}})
        .project({{'goodsInfo': 1,'payInfo.feeInfo': 1}})
        .addFields({{foodIDs: $.reduce({{input: '$goodsInfo.record',initialValue: [],in: $.concatArrays(['$$value',['$$this._id']]),}})}})
        .lookup({{let: {{foodIDs: '$foodIDs'}},from: 'food',
        pipeline: $.pipeline()
        .match(_.expr($.in(['$_id', '$$foodIDs']))).project({{typeName: 1}})
        .done(),as: 'foodInfo'}})
        .project({{foodIDs: 0,_id: 0}}).end()
        '''
        collection_name = 'orders'
        res = Database.aggregate(collection_name,query)
        if res['errcode'] == 0:
            return res['data']
        else:
            raise XMUORDERException('读取数据错误')

    @classmethod
    def price_cal(cls, keyName: str):
        '''
        计算商品总价
        '''
        res = cls.get_order_data('20210601')
        price_total = Decimal(0)
        for data in res:
            print(data)
            try:
                data_dict = json.loads(data)
                price = Decimal(data_dict['payInfo']['feeInfo'][keyName]['$numberInt'])
                price_total = price_total + price
                return price_total
            except Exception as e:
                logger.debug(f'计算价格失败{e}')
    @classmethod
    def price_cal_classify(cls,type=None):
        '''
        根据类别计算商品价格
        '''
        price_dict = {}
        res = cls.get_order_data('20210601')
        try:
            for record in res:
                record_dict = json.loads(record)
                for index,data in enumerate(record_dict['foodInfo']):
                    temp = record_dict['goodsInfo']['record'][index]
                    price_temp = Decimal(temp['num']['$numberInt']) * Decimal(temp['price']['$numberDouble'])
                    if data['typeName'] not in price_dict.keys():
                        price_dict[data['typeName']] = price_temp
                    else:
                        price_dict[data['typeName']] = price_dict[data['typeName']] + price_temp
            if type == None:
                return price_dict
            else:
                if type in price_dict.keys():
                    return price_dict[type]
                else:
                    raise XMUORDERException('输入的type不正确')
        except Exception as e:
            logger.debug(f'计算分类价格失败{e}')