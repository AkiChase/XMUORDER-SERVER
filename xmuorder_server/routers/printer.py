import asyncio
import json
import time
from datetime import datetime
from enum import unique, Enum
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
from ..weixin.database import Database

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


class PrinterCIDModel(BaseModel):
    cID: str


class PrintAcceptOrderModel(BaseModel):
    outTradeNo: str


class PrintOrderNoticeType(str, Enum):
    new = 'new'
    cancel = 'cancel'
    refund = 'refund'


class PrintOrderNoticeModel(BaseModel):
    cID: str
    notice_type: PrintOrderNoticeType


@router.post("/addPrinter")
async def add_printer_to_canteen(data: AddPrinterModel, verify=Depends(dependencies.code_verify_aes_depend)):
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
        )])

        if len(res['data']['ok']) > 0:
            sql = '''
                insert into printer (sn, cID, `key`)
                VALUES (%(sn)s, %(cID)s, %(key)s)
            '''
            Mysql.execute_only(conn, sql, sn=data.sn, cID=data.cID, key=data.key)
            conn.commit()
            logger.success(f'{canteen_name}添加打印机成功 -sn={data.sn}')
            return SuccessInfo(msg='添加成功').to_dict()
        else:
            err_msg: str = res['data']['no'][0]
            #   被添加过则修改本地数据库信息（实现更换打印机所属餐厅）
            if err_msg.find('被添加过') > -1:
                sql = '''
                insert into printer (sn ,cID, `key`)
                    VALUES (%(sn)s, %(cID)s, %(key)s)
                ON DUPLICATE KEY UPDATE
                    cID=%(cID)s, `key`=%(key)s
                '''
                Mysql.execute_only(conn, sql, sn=data.sn, cID=data.cID, key=data.key)
                conn.commit()
                logger.success(f'{canteen_name}添加已绑定打印机 -sn={data.sn}')
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
async def get_printer_state_by_cid(data: PrinterCIDModel, verify=Depends(dependencies.code_verify_aes_depend)):
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


@router.post("/printAcceptOrder")
async def print_accept_order_by_cid(data: PrintAcceptOrderModel, verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    try:
        #   获取订单
        res = Database.query('orders', f"where({{'orderInfo.outTradeNo':'{data.outTradeNo}'}}).limit(1).get()")
        order_json = json.loads(res['data'][0])

        cid = order_json['goodsInfo']['shopInfo']['cID']
        shop_name = order_json['goodsInfo']['shopInfo']['name']
        order = Printer.OrderModel(
            shop_name=shop_name,
            get_food_way='外卖' if order_json['deliverInfo']['isDelivery'] is True else '自取',
            user_name=order_json['userInfo']['name'],
            user_phone=order_json['userInfo']['phone'],
            get_food_address=order_json['getFoodInfo']['place'],
            confirm_time=datetime.strftime(datetime.strptime(
                order_json['orderInfo']['timeInfo']['confirmTime'], '%Y%m%d%H%M%S'), '%Y-%m-%d %H:%M:%S'),
            goods_list=[
                [goods['food'], goods['price'], goods['num']]
                for goods in order_json['goodsInfo']['record']
            ],
            goods_price=f"{'%.2f' % sum([x['price'] * x['num'] for x in order_json['goodsInfo']['record']])}元",
            user_note='暂无备注',
            out_trade_no=data.outTradeNo
        )

        out = await __print_by_cid(_conn=conn, _cid=cid, _print_fn=Printer.print_accept_order, order=order)
        logger.success(f'打印接单小票成功×{len(out)} -{shop_name}')
        return out

    except WithMsgException as e:
        logger.debug(f'打印接单小票失败-{e.msg}')
        raise HTTPException(status_code=400, detail=e.msg)
    except Exception as e:
        logger.debug(f'打印接单小票失败 outTradeNo-{data.outTradeNo} -{e}')
        raise HTTPException(status_code=400, detail='获取餐厅打印机状态失败')
    finally:
        conn.close()


@router.post("/printOrderNotice")
async def print_new_order_notice_by_cid(data: PrintOrderNoticeModel,
                                        verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    notice_dict = {
        'new': ('打印新订单提醒', Printer.print_new_order_notice),
        'cancel': ('打印取消订单提醒', Printer.print_cancel_order_notice),
        'refund': ('打印退款订单提醒', Printer.print_refund_order_notice),
    }

    try:
        out = await __print_by_cid(_conn=conn, _cid=data.cID, _print_fn=notice_dict[data.notice_type][1])
        logger.success(f'{notice_dict[data.notice_type][0]}成功×{len(out)} cID-{data.cID}')
        return out

    except Exception as e:
        logger.debug(f'{notice_dict[data.notice_type][0]}失败 cID-{data.cID} -{e}')
        raise HTTPException(status_code=400, detail=f'{notice_dict[data.notice_type][0]}失败')
    finally:
        conn.close()


async def __print_by_cid(_conn, _cid: str, _print_fn: callable, **kwargs):
    """
    打印到餐厅的所有打印机
    :param _conn: mysql 连接
    :param _cid: 餐厅id
    :param _print_fn: 打印函数
    :param kwargs: 打印函数的参数 (不需要sn)
    :return:
    """
    sql = 'select sn from printer where cID = %(cID)s;'
    res = Mysql.execute_fetchall(_conn, sql, cID=_cid)

    if not len(res):
        return {
            'success': True,
            'data': []
        }
    #   获取打印机状态
    out = await Printer.query_printer_list_state([x[0] for x in res])
    for i in range(len(res)):
        out[i]['sn'] = res[i][0]
        # 视情况分别打印
        if out[i]['state'] == 1:
            print_res = _print_fn(sn=res[i][0], **kwargs)
            out[i]['print_state'] = True
            out[i]['print_msg'] = '打印任务已发起'
            out[i]['print_order_id'] = print_res['data']
        else:
            out[i]['print_state'] = False
            out[i]['print_msg'] = '云打印机未在线'

    return out


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

    class OrderModel:
        shop_name: str
        get_food_way: str
        user_name: str
        user_phone: str
        get_food_address: str
        confirm_time: str
        goods_list: list  # [[商品名, 单价, 数量],...]
        goods_price: str
        user_note: str
        out_trade_no: str

        def __init__(self, shop_name: str,
                     get_food_way: str,
                     user_name: str,
                     user_phone: str,
                     get_food_address: str,
                     confirm_time: str,
                     goods_list: list,  # [[商品名, 单价, 数量],...]
                     goods_price: str,
                     user_note: str,
                     out_trade_no: str):
            self.shop_name = shop_name
            self.get_food_way = get_food_way
            self.user_name = user_name
            self.user_phone = user_phone
            self.get_food_address = get_food_address
            self.confirm_time = confirm_time
            self.goods_list = goods_list
            self.goods_price = goods_price
            self.user_note = user_note
            self.out_trade_no = out_trade_no

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
    def _print_msg(cls, sn: str, content: str, times: int = 1):
        """
        小票机打印
        58mm的机器,一行打印16个汉字,32个字母
        :param sn: 打印机编号
        :param content: 打印内容,不能超过5000字节 具体见api接口教程
        :param times: 打印次数默认为1
        """
        return cls.__request({
            'apiname': 'Open_printMsg',
            'sn': sn,
            'content': content,
            'times': times
        })

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

                if res_json['data'].find('工作状态正常') > -1:
                    out_state['state'] = 1
                elif res_json['data'].find('工作状态不正常') > -1:
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
    def print_new_order_notice(cls, sn: str):
        return cls._print_msg(sn, '\n'.join([
            '<CB>新订单通知</CB>', '<C>请进入XMU智能点餐小程序接单/拒单<C><BR>'
        ]))

    @classmethod
    def print_cancel_order_notice(cls, sn: str):
        return cls._print_msg(sn, '\n'.join([
            '<CB>取消订单通知</CB>', '<C>提示：此订单餐厅尚未接单<C>', '<AUDIO-CANCEL>'
        ]))

    @classmethod
    def print_refund_order_notice(cls, sn: str):
        return cls._print_msg(sn, '\n'.join([
            '<CB>申请退款通知</CB>', '<C>请进入小程序管理端"反馈"页面处理<C>', '<AUDIO-REFUND>'
        ]))

    @classmethod
    def print_accept_order(cls, sn: str, order: OrderModel):
        #   头部
        content = ['<CB>XMU智能点餐</CB>']
        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.LINE)
        #   基本信息
        for x in (
                ['餐厅名称:', order.shop_name],
                ['取餐方式:', order.get_food_way, [None, 'L']],
                'line',
                ['用户名称:', order.user_name, [None, 'L']],
                ['联系方式:', order.user_phone, [None, 'L']],
                ['取餐地点:', order.get_food_address, [None, 'BOLD']],
                ['接单时间:', order.confirm_time]
        ):
            if x == 'line':
                content += cls.LineFormat.format(mode=cls.LineFormat.Mode.LINE)
            # elif x == 'BR':
            #     content.append('')  # 因为换行符会在join时添加
            else:
                content += cls.LineFormat.format(
                    mode=cls.LineFormat.Mode.TWO_PART,
                    part_content_list=x[0:2],
                    width_list=[10, 20],
                    mode_list=['l', 'r'],
                    label_list=None if len(x) == 2 else x[2]
                )

        #   商品信息
        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.DOUBLE_LINE)
        content += cls.LineFormat.format(
            mode=cls.LineFormat.Mode.FOUR_PART,
            part_content_list=['商品名称', '单价', '数量', '金额'],
            width_list=[14, 5, 4, 6],
            mode_list=['l', 'c', 'c', 'c']
        )
        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.LINE)
        for x in order.goods_list:
            content += cls.LineFormat.format(
                mode=cls.LineFormat.Mode.FOUR_PART_GOODS,
                width_list=[14, 5, 4, 6],
                goods_info=cls.LineFormat.GoodsInfoModel(x[0], x[1], x[2])
            )

        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.LINE)
        content += cls.LineFormat.format(
            mode=cls.LineFormat.Mode.TWO_PART,
            part_content_list=['合计(未计其他费用):', order.goods_price],
            width_list=[20, 10],
            mode_list=['l', 'r'],
            label_list=[None, 'BOLD']
        )
        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.STAR_LINE)
        content += [
            '<L>用户备注:</L>',
            order.user_note
        ]
        content += cls.LineFormat.format(mode=cls.LineFormat.Mode.STAR_LINE)
        content.append(f'<QR>outTradeNo={order.out_trade_no}</QR>')
        return cls._print_msg(sn, '\n'.join(content))

    class LineFormat:
        """
        打印内容格式化
        """
        LINE_WIDTH = 32

        @unique
        class Mode(Enum):
            TWO_PART = 1  # 左右对齐排版
            THREE_PART = 2  # 按宽度对齐分成3部分排版
            FOUR_PART = 3  # 按宽度对齐分成4部分排版
            FOUR_PART_GOODS = 4  # 按宽度对齐分成4部分排版 填入商品信息
            LINE = 5  # 分割线 -------------
            DOUBLE_LINE = 6  # 分割线 =============
            STAR_LINE = 7

        class GoodsInfoModel:
            name: str
            price: str
            num: str
            sum_price: str

            def __init__(self, name: str, price: float, num: int):
                self.name = name
                self.price = "%.2f" % price
                self.num = str(num)
                self.sum_price = "%.2f" % (price * num)

        @classmethod
        def format(cls, mode: Mode, **kwargs) -> list[str]:
            """
            根据模式对内容进行格式化输出
            :param mode: Mode枚举
            :param kwargs: 格式化函数所需参数
            """
            enum_dict = {
                1: cls._two_part,
                2: cls._three_part,
                3: cls._four_part,
                4: cls._four_part_goods,
                5: cls.__line,
                6: cls.__double_line,
                7: cls.__star_line
            }
            return enum_dict[mode.value](**kwargs)

        @staticmethod
        def __part_join(part_list, width_list, part_num: int, space_num: int, label_list: list):
            """
            四个部分用空格相连，若某个部分不存在文字用空格代替
            """
            len_list = [len(x) for x in part_list]
            out = []
            line_count = max(len_list)
            for line_index in range(line_count):
                for i in range(part_num):
                    #   为第i个部分补充空内容
                    if len_list[i] < line_index + 1:
                        part_list[i].append(' ' * width_list[i])
                    #   为第i个部分补充标签
                    label = label_list[i]
                    if label is not None:
                        part_list[i][line_index] = f'<{label}>{part_list[i][line_index]}</{label}>'

                out.append((' ' * space_num).join([part[line_index] for part in part_list]))
            return out

        @classmethod
        def _two_part(cls,
                      part_content_list: list[str],
                      width_list: list[int] = None,
                      mode_list: list[str] = None,
                      label_list: list[str] = None) -> list[str]:
            """
            分两部分显示 实现超出字数的自动换下一行对齐处理，同时保持各列进行对齐
            :param part_content_list:每个部分的信息
            :param width_list:每部分宽度信息
            :param mode_list:每部分对齐方式
            :param label_list:每部分补充的打印机格式化标签 如 'B'代表<B></B>
            """
            if width_list is None:
                width_list = [15, 15]
            if sum(width_list) > cls.LINE_WIDTH:
                raise Exception('两部分宽度之和超过行总宽度')
            if label_list is None:
                label_list = [None] * 2
            space_num = cls.LINE_WIDTH - sum(width_list)

            if mode_list is None:
                mode_list = ['c', 'c']

            part_list = [
                cls.__warp_result(part_content_list[i], width_list[i], mode=mode_list[i]) for i in range(2)
            ]
            return cls.__part_join(part_list, width_list, 2, space_num, label_list)

        @classmethod
        def _three_part(cls,
                        part_content_list: list[str],
                        width_list: list[int] = None,
                        mode_list: list[str] = None,
                        label_list: list[str] = None) -> list[str]:
            """
            分三部分显示 实现超出字数的自动换下一行对齐处理，同时保持各列进行对齐
            :param part_content_list:每个部分的信息
            :param width_list:每部分宽度信息
            :param mode_list:每部分对齐方式
            :param label_list:每部分补充的打印机格式化标签 如 'B'代表<B></B>
            """
            if width_list is None:
                width_list = [18, 8, 2]
            if sum(width_list) > cls.LINE_WIDTH:
                raise Exception('三部分宽度之和超过行总宽度')
            if label_list is None:
                label_list = [None] * 3
            space = cls.LINE_WIDTH - sum(width_list)
            if space % 2 != 0:
                raise Exception('剩余部分宽度不是2的倍数')
            space_num = space // 2

            if mode_list is None:
                mode_list = ['l', 'r', 'r', 'r']

            part_list = [
                cls.__warp_result(part_content_list[i], width_list[i], mode=mode_list[i]) for i in range(3)
            ]
            return cls.__part_join(part_list, width_list, 3, space_num, label_list)

        @classmethod
        def _four_part(cls,
                       part_content_list: list[str],
                       width_list: list[int] = None,
                       mode_list: list[str] = None,
                       label_list: list[str] = None) -> list[str]:
            """
            商品信息分四部分显示 实现商品超出字数的自动换下一行对齐处理，同时保持各列进行对齐
            :param part_content_list:每个部分的信息
            :param width_list:每部分宽度信息
            :param mode_list:每部分对齐方式
            :param label_list:每部分补充的打印机格式化标签 如 'B'代表<B></B>
            """
            if width_list is None:
                width_list = [14, 6, 3, 6]
            if sum(width_list) > cls.LINE_WIDTH:
                raise Exception('四部分宽度之和超过行总宽度')
            if label_list is None:
                label_list = [None] * 4
            space = cls.LINE_WIDTH - sum(width_list)
            if space % 3 != 0:
                raise Exception('剩余部分宽度不是3的倍数')
            space_num = space // 3

            if mode_list is None:
                mode_list = ['l', 'r', 'r', 'r']

            part_list = [
                cls.__warp_result(part_content_list[i], width_list[i], mode=mode_list[i]) for i in range(4)
            ]
            return cls.__part_join(part_list, width_list, 4, space_num, label_list)

        @classmethod
        def _four_part_goods(cls,
                             goods_info: GoodsInfoModel,
                             width_list: list[int] = None,
                             mode_list: list[str] = None,
                             label_list: list[str] = None) -> list[str]:
            """
            使用商品信息来调用four_part
            """
            part_content_list = [
                goods_info.name, goods_info.price, goods_info.num, goods_info.sum_price
            ]
            return cls._four_part(part_content_list, width_list, mode_list, label_list)

        @classmethod
        def __line(cls) -> list[str]:
            return ['-' * cls.LINE_WIDTH]

        @classmethod
        def __double_line(cls) -> list[str]:
            return ['=' * cls.LINE_WIDTH]

        @classmethod
        def __star_line(cls) -> list[str]:
            return ['*' * cls.LINE_WIDTH]

        @staticmethod
        def __wrap(width: int, output: list, line: bytes) -> bytes:
            """
            换行
            :param width: 行的最大宽度
            :param output: 旧行输出
            :param line: 需要换行的内容
            :return: 换行后剩余部分
            """
            try:
                output.append(line[0:width].decode('gbk'))
                new_line = line[width:]
            except:
                output.append(line[0:width - 1].decode('gbk') + ' ')
                new_line = line[width - 1:]
            return new_line

        @classmethod
        def __warp_result(cls, content: str, width: int, mode: str = 'l'):
            """
            将文本按宽度换行，返回换行结果列表
            :param content: 文本
            :param width: 宽度
            :param mode: 对齐方式 左 中 右 'l','c','r'
            :return:
            """
            gbk_line = content.encode('gbk')
            out = []
            new_line = gbk_line
            while True:
                if len(new_line) <= width:
                    ori_line = new_line.decode('gbk')
                    padding_len = width - len(new_line)
                    if mode == 'l':
                        f = ori_line.ljust
                    elif mode == 'r':
                        f = ori_line.rjust
                    else:
                        f = ori_line.center
                    out.append(f(len(ori_line) + padding_len, ' '))
                    break
                new_line = cls.__wrap(width, out, new_line)
            return out
