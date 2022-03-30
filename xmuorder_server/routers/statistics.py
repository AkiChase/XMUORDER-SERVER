from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import dependencies
from ..logger import Logger
from ..weixin.database import Database
from ..common import XMUORDERException, WithMsgException

from decimal import Decimal
import json

router = APIRouter()
logger: Logger


class OrderStatisticsModel(BaseModel):
    """
    订单统计接口
    """
    cID: str
    begin_date: str
    end_date: str


@router.on_event("startup")
async def __init():
    #   获取默认日志
    global logger
    logger = Logger('统计模块')


@router.post("/orderInfo")
async def order_info(data: OrderStatisticsModel, verify=Depends(dependencies.code_verify_aes_depend)):
    """
    统计订单的营业额、销量等信息
    """
    try:
        if data.begin_date > data.end_date:
            raise WithMsgException('统计的起始日期大于终止日期')

        out = {
            'success': True,
            'cID': data.cID,
            'beginTime': data.begin_date + '0000',
            'endTime': data.end_date + '2400'
        }

        order_data = OrderStatistics.get_order_data(cid=data.cID, begin_date=data.begin_date, end_date=data.end_date)
        cal_dict = OrderStatistics.cal_by_class(order_data)
        out['data'] = [{'typeName': k, **v} for k, v in cal_dict.items()]

        return out
    except WithMsgException as e:
        logger.error(f'[订单统计]-{e}-cID:{data.cID} -endData:{data.end_date}')
        raise HTTPException(status_code=400, detail=e.msg)

    except Exception as e:
        logger.error(f'[订单统计]-{e}-cID:{data.cID} -endData:{data.end_date}')
        raise HTTPException(status_code=400, detail="订单统计失败")


class OrderStatistics:
    """
    订单统计，营业额、销量
    """

    @staticmethod
    def get_order_data(cid: str, begin_date: str, end_date: str) -> list[str]:
        """
        获取订单数据库内容，同步分页循环获取，返回list[json]
        """

        #   分页
        count_query = f'''
        where({{
            'orderInfo.orderState': 'SUCCESS', 'payInfo.tradeState': 'SUCCESS',
            'goodsInfo.shopInfo.cID':'{cid}',
            'orderInfo.timeInfo.confirmTime': _.and(_.gte('{begin_date + '0000'}'), _.lt('{end_date + '2400'}'))
        }}).count()
        '''
        total_count = Database.count('orders', count_query)['count']
        page_size = 25
        total_page = int((total_count - 1) / page_size + 1)

        #   构建查询语句
        query = f'''
        aggregate().match({{'orderInfo.orderState': 'SUCCESS', 'payInfo.tradeState': 'SUCCESS',
        'goodsInfo.shopInfo.cID':'{cid}',
        'orderInfo.timeInfo.confirmTime':_.and(_.gte('{begin_date + '0000'}'), _.lte('{end_date + '2400'}'))
        }})
        %%skip_limit_words%%
        '''
        query += '''
        .project({'goodsInfo': 1,'payInfo.feeInfo': 1})
        .addFields({foodIDs: $.reduce({input: '$goodsInfo.record',initialValue: []
        ,in: $.concatArrays(['$$value',['$$this._id']]),})})
        .lookup({let: {foodIDs: '$foodIDs'},from: 'food',pipeline: $.pipeline()
        .match(_.expr($.in(['$_id', '$$foodIDs']))).project({typeName: 1})
        .done(),as: 'foodInfo'})
        .project({foodIDs: 0,_id: 0}).end()
        '''

        #   查询
        out = []
        for page_num in range(total_page):
            new_query = query.replace('%%skip_limit_words%%', f'.skip({page_num * page_size}).limit({page_size})')
            res = Database.aggregate('orders', new_query)
            out += res['data']

        return out

    @staticmethod
    def cal_by_class(orders_list: list[str]) -> dict:
        """
        根据类别计算商品价格
        """
        out_dict = {}
        try:
            for record in orders_list:
                record_dict = json.loads(record)
                for index, data in enumerate(record_dict['foodInfo']):
                    #   计算
                    temp = record_dict['goodsInfo']['record'][index]
                    price = Decimal(temp['num']['$numberInt']) * Decimal(temp['price']['$numberDouble'])
                    num = int(temp['num']['$numberInt'])
                    #   记录
                    if data['typeName'] not in out_dict.keys():
                        out_dict[data['typeName']] = {
                            'income': price,
                            'salesAmount': num
                        }
                    else:
                        out_dict[data['typeName']]['income'] += price
                        out_dict[data['typeName']]['salesAmount'] += num
            return out_dict
        except Exception as e:
            raise XMUORDERException(('根据类别计算商品价格失败', e))
