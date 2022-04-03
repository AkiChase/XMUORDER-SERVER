import asyncio
import time
from datetime import datetime
from hashlib import sha1
from typing import Optional

import httpx
import requests
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .. import dependencies
from ..common import WithMsgException, SuccessInfo
from ..config import GlobalSettings
from ..database import Mysql
from ..logger import Logger

router = APIRouter()
logger: Logger


@router.on_event("startup")
async def __init():
    global logger
    logger = Logger('云打印机模块')
    Printer.init()


class AddPrinterModel(BaseModel):
    sn: str  # 打印机编号
    key: str  # 打印机识别码
    cID: str  # 所在餐厅cID
    card_num: Optional[str]  # 流量卡号 选填


class GetPrinterStateModel(BaseModel):
    cID: str


@router.post("/addPrinter")
async def add_printer(data: AddPrinterModel, verify=Depends(dependencies.code_verify_aes_depend)):
    """
    添加餐厅打印机
    """
    conn = Mysql.connect()
    try:
        sql = 'select name from canteen where cID = %(cID)s limit 1;'
        name_res = Mysql.execute_fetchone(conn, sql, cID=data.cID)
        if name_res is None:
            raise WithMsgException('餐厅信息不存在')
        canteen_name = name_res[0]
        res = Printer.add_printer([Printer.PrinterModel(
            sn=data.sn,
            key=data.key,
            card_num=data.card_num,
            name=canteen_name
        )])

        if len(res['data']['ok']) > 0:
            sql = '''
                insert into printer (sn, cID, `key`)
                VALUES (%(sn)s, %(cID)s, %(key)s)
            '''
            Mysql.execute_only(conn, sql, sn=data.sn, cID=data.cID, key=data.key)
            conn.commit()
            return SuccessInfo(msg='添加成功').to_dict()
        else:
            err_msg: str = res['data']['no'][0]
            if err_msg.find('被添加过') > -1:
                return SuccessInfo(msg='打印机已添加').to_dict()

            raise WithMsgException(err_msg[err_msg.find('错误') + 3:-1])

    except WithMsgException as e:
        logger.debug(f'添加打印机失败-{e.msg}')
        raise HTTPException(status_code=400, detail=e.msg)
    except Exception as e:
        logger.debug(f'添加打印机失败-{e}')
        raise HTTPException(status_code=400, detail='添加打印机失败')
    finally:
        conn.close()


@router.post("/getPrinterState")
async def get_printer_state(data: GetPrinterStateModel, verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    try:
        sql = 'select sn from printer where cID = %(cID)s;'
        res = Mysql.execute_fetchall(conn, sql, cID=data.cID)

        if not len(res):
            return {
                'success': True,
                'data': []
            }

        out = await Printer.query_printer_list_state([x[0] for x in res])
        for i in range(len(res)):
            out[i]['sn'] = res[i][0]
        return {
            'success': True,
            'data': out
        }

    except WithMsgException as e:
        logger.debug(f'获取餐厅打印机状态失败-{e.msg}')
        raise HTTPException(status_code=400, detail=e.msg)
    except Exception as e:
        logger.debug(f'获取餐厅打印机状态失败 cID-{data.cID} -{e}')
        raise HTTPException(status_code=400, detail='获取餐厅打印机状态失败')
    finally:
        conn.close()


class Printer:
    """
    云打印机封装
    api接口: http://www.feieyun.com/open/index.html
    """
    url = 'http://api.feieyun.cn/Api/Open/'
    USER: str
    UKEY: str

    class PrinterModel:
        """
        打印机信息模板
        """
        sn: str  # 打印机编号
        key: str  # 打印机识别码
        name: Optional[str]  # 备注名称
        card_num: Optional[str]  # 流量卡号

        def __init__(self, sn: str, key: str, name: str = None, card_num: str = None):
            self.sn = sn
            self.key = key
            self.name = name
            self.card_num = card_num

        def __str__(self):
            out = [self.sn, self.key]
            if self.name is not None:
                out.append(self.name)
            if self.card_num is not None:
                out.append(self.card_num)
            return '# '.join(out)

    @classmethod
    def init(cls):
        #   读取密钥
        global_setting = GlobalSettings.get()
        cls.USER = global_setting.printer_user
        cls.UKEY = global_setting.printer_key

    @classmethod
    def __signature(cls, ts: str):
        """
        获取签名
        """
        s = sha1()
        s.update((cls.USER + cls.UKEY + ts).encode())
        return s.hexdigest()

    @classmethod
    def __request(cls, params: dict) -> dict:
        ts = str(int(time.time()))
        post_data = {
            'user': cls.USER,
            'sig': cls.__signature(ts),
            'stime': ts,
        }
        post_data.update(params)
        res = requests.post(cls.url, data=post_data, timeout=30)
        if res.status_code != 200:
            raise Exception(f'status code = {res.status_code}')
        res_json = res.json()
        if 'ret' in res_json and res_json['ret'] != 0:
            raise Exception(res_json['msg'])
        return res.json()

    @classmethod
    def __httpx(cls, client: httpx.AsyncClient, params: dict):
        ts = str(int(time.time()))
        post_data = {
            'user': cls.USER,
            'sig': cls.__signature(ts),
            'stime': ts,
        }
        post_data.update(params)
        return client.post(cls.url, data=post_data, timeout=30)

    @classmethod
    def add_printer(cls, printer_list: list) -> dict:
        """
        批量添加打印机
        :param printer_list: 打印机信息的list 信息使用 PrinterModel
        """
        return cls.__request({
            'apiname': 'Open_printerAddlist',
            'printerContent': '\n'.join([str(x) for x in printer_list])
        })

    @classmethod
    def del_printer(cls, sn_list: list[str]) -> dict:
        """
        批量删除打印机
        :param sn_list: 打印机编号list
        """
        return cls.__request({
            'apiname': 'Open_printerDelList',
            'snlist': '-'.join(sn_list)
        })

    @classmethod
    def clear_printer_task(cls, sn: str) -> dict:
        """
        清空指定打印机的待打印任务队列
        """

        return cls.__request({
            'apiname': 'Open_delPrinterSqs',
            'sn': sn
        })

    @classmethod
    def query_order_state(cls, order_id):
        """
        根据订单ID,查询订单是否打印成功,订单ID由打印小票接口返回
        """
        return cls.__request({
            'apiname': 'Open_queryOrderState',
            'orderid': order_id
        })

    @classmethod
    def query_printer_state(cls, sn):
        """
        查询指定打印机状态，返回该打印机在线或离线，正常或异常的信息 (异常一般是无纸)
        """
        return cls.__request({
            'apiname': 'Open_queryPrinterStatus',
            'sn': sn
        })

    @classmethod
    async def query_printer_list_state(cls, sn_list):
        """
        批量查询打印机状态
        """
        async with httpx.AsyncClient() as client:
            task_list = [
                cls.__httpx(client, {
                    'apiname': 'Open_queryPrinterStatus',
                    'sn': sn
                }) for sn in sn_list
            ]

            res_list = await asyncio.gather(*task_list)

        out = []
        for res in res_list:
            try:
                if res.status_code != 200:
                    raise Exception()
                res_json = res.json()
                if 'ret' in res_json and res_json['ret'] != 0:
                    raise Exception()

                out_state = {
                    'success': True,
                    'msg': res_json['data'],
                }

                if res_json['data'] == '在线，工作状态正常':
                    out_state['state'] = 1
                elif res_json['data'] == '在线，工作状态不正常':
                    out_state['state'] = 0
                else:  # 离线
                    out_state['state'] = -1
                out.append(out_state)
            except:
                out.append({
                    'success': False,
                    'msg': '获取失败',
                })
        return out

    @classmethod
    def query_order_by_date(cls, sn: str, date: datetime):
        """
        查询指定打印机某天的订单详情，返回已打印订单数和等待打印数
        """
        return cls.__request({
            'apiname': 'Open_queryOrderInfoByDate',
            'sn': sn,
            'date': date.strftime('%Y-%m-%d')
        })

    @classmethod
    def print_msg(cls, sn: str, content: str, times: int = 1):
        """
        小票机打印
        :param sn: 打印机编号
        :param content: 打印内容,不能超过5000字节 具体见api接口教程
        :param times: 打印次数默认为1
        :return:
        """
        return cls.__request({
            'apiname': 'Open_printMsg',
            'sn': sn,
            'content': content,
            'times': times
        })
