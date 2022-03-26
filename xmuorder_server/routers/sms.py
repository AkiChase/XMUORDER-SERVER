"""
短信服务相关
"""
import random
import re
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from tencentcloud.common import credential
from tencentcloud.sms.v20210111 import sms_client, models

from .. import dependencies
from ..common import SuccessInfo, XMUORDERException
from ..config import GlobalSettings
from ..database import Mysql
from ..logger import Logger
from ..scheduler import Scheduler, Task

router = APIRouter()
logger: Logger


class SendSmsModel(BaseModel):
    """
    发送信息模板
    """
    cID_list: list[str]
    time1: Optional[str] = 3
    time2: Optional[str] = 10


class SmsVerificationCodeModel(BaseModel):
    """
    发送验证码模板
    """
    phone: str


class BindCanteenSmsModel(BaseModel):
    """
    绑定餐厅通知手机号模板
    """
    cID: str
    cName: str
    phone: str
    sms_code: str


@router.on_event("startup")
async def __init():
    #   获取默认日志
    global logger
    logger = Logger('短信模块')
    #   添加任务
    Scheduler.add(Task.clear_phone_verification_task, job_name='清空验证码数据',
                  trigger='cron', hour="2", minute="0", second='0')


@router.post("/send")
async def send_sms(data: SendSmsModel, verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    try:
        cid_list = [f"'{x}'" for x in data.cID_list]
        for x in cid_list:
            if x.find(' ') > -1:
                raise XMUORDERException("cID列表异常")

        #   过滤出需要发送的电话号码
        sql = f'''
        select c.cID, p.phone, c.lastSendMsgTime
        from canteen c
                 left join phone p on c.cID = p.cID
        where c.cID in {f"({','.join(cid_list)})"}
            and TIMESTAMPDIFF(minute, c.lastSendMsgTime, NOW()) > 30;
        '''

        res = Mysql.execute_fetchall(conn, sql=sql)
        phone_list = set([line[1] for line in res if line[1] is not None])

        #   更新 lastSendMsgTime
        sql = f'''
        update canteen set lastSendMsgTime = NOW()
        where cID in {f"({','.join(cid_list)})"};
        '''
        Mysql.execute_only(conn, sql)

        #   发送短信
        res = send_message(list(phone_list), time1=data.time1, time2=data.time2)
        return SuccessInfo(msg='Sms request success',
                           data={'SendStatusSet': res.SendStatusSet}).to_dict()

    except Exception as e:
        logger.debug(f'sms发送商家通知短信失败-{e}')
        raise HTTPException(status_code=400, detail="Message sending failed")
    finally:
        conn.close()


@router.post("/phoneVerificationCode")
async def phone_verification_code(data: SmsVerificationCodeModel, verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    try:
        # 再次简单核验电话号码，防止注入等问题
        assert re.match(r'\+861\d{10}', data.phone) is not None

        # 验证码
        code = str(random.randint(100000, 999999))

        sql = '''
        select phone, code, expiration, lastSendTime, sendTimes
        from phone_verification where phone=%(phone)s
        '''
        res = Mysql.execute_fetchone(conn, sql, phone=data.phone)
        if res is None:
            sql = '''
            insert into phone_verification (phone, code, expiration, lastSendTime, sendTimes)
            VALUES (%(phone)s, %(code)s, DATE_ADD(now(), interval 5 minute), now(), 0)
            '''
        else:
            if res[4] >= 5:
                raise XMUORDERException('此号码已达到今日发送验证码次数上限')

            # 2min内发送过验证码则退出
            sec = (datetime.now() - res[3]).seconds
            if sec < 2 * 60:
                raise XMUORDERException('此号码短信发送过于频繁，请稍后再试')

            # 5min后验证码过期
            sql = '''
            UPDATE phone_verification
                set phone=%(phone)s, code=%(code)s, sendTimes=sendTimes+1,
                expiration=DATE_ADD(now(), interval 5 minute),
                lastSendTime=NOW()
            where
                phone=%(phone)s;
            '''

        Mysql.execute_only(conn, sql, phone=data.phone, code=code)

        # 发送验证码短信
        res = send_verification_code(data.phone, code)
        conn.commit()

        # return SuccessInfo(msg='Verification code request success',
        #                    data={'SendStatusSet': res}).to_dict()
        logger.debug(f'验证码发送成功-phone:{data.phone}')
        return SuccessInfo(msg='Verification code request success',
                           data={'SendStatusSet': res.SendStatusSet}).to_dict()

    except XMUORDERException as e:
        logger.debug(f'sms发送验证码短信失败-{e}')
        raise HTTPException(status_code=400, detail=e.msg)
    except Exception as e:
        logger.debug(f'sms发送验证码短信失败-{e}')
        raise HTTPException(status_code=400, detail="send phone verification code failed")
    finally:
        conn.close()


@router.post("/bind")
async def bind_canteen_sms(data: BindCanteenSmsModel, verify=Depends(dependencies.code_verify_aes_depend)):
    conn = Mysql.connect()
    try:
        # 再次简单核验电话号码，防止注入等问题
        assert re.match(r'\+861\d{10}', data.phone) is not None

        sql = '''
        select phone, code, expiration from phone_verification
        where phone=%(phone)s; 
        '''
        res: tuple[str, str, datetime] = Mysql.execute_fetchone(conn, sql, phone=data.phone)
        # 有此号码记录
        assert res is not None
        # 验证码未过期
        assert (datetime.now() - res[2]).seconds > 5 * 60

        sql = '''
        # 更新此号码所在餐厅
        insert into canteen (cID, name)
            VALUES (%(cID)s, %(name)s)
        ON DUPLICATE KEY UPDATE
            name=%(name)s;
        # 插入phone表
        insert into phone (cID, phone)
            values (%(cID)s, %(phone)s)
        '''

        Mysql.execute_only(conn, sql, cID=data.cID, name=data.cName, phone=data.phone)
        conn.commit()

        logger.success(f'[短信服务]绑定餐厅短信通知成功-phone:{data.phone}')
        return SuccessInfo(msg='Bind sms notification success',
                           data={'phone': data.phone}).to_dict()
    except Exception as e:
        logger.debug(f'手机号绑定餐厅短信通知失败-{e}')
        raise HTTPException(status_code=400, detail="Bind sms notification failed")
    finally:
        conn.close()


def send_tencent_sms(appid: str, sign_name: str, template_id: str,
                     template_params: list[str], phone_list: list[str]):
    """
    腾讯云发送短信
    :param appid: 短信应用ID
    :param sign_name: 短信签名内容
    :param template_id: 模板 ID
    :param template_params: 模板参数
    :param phone_list: 接收号码列表
    :return: SendSmsResponse
    """
    settings = GlobalSettings.get()
    # 实例化一个认证对象，入参需要传入腾讯云账户密钥对secretId，secretKey。
    cred = credential.Credential(settings.secret_id, settings.secret_key)

    # 实例化要请求产品(以sms为例)的client对象 第二个参数为地域
    client = sms_client.SmsClient(cred, "ap-guangzhou")

    # 实例化一个请求对象，根据调用的接口和实际情况，可以进一步设置请求参数
    req = models.SendSmsRequest()

    # 短信应用ID: 短信SdkAppId在 [短信控制台] 添加应用后生成的实际SdkAppId，示例如1400006666
    req.SmsSdkAppId = appid
    # 短信签名内容: 使用 UTF-8 编码，必须填写已审核通过的签名，签名信息可登录 [短信控制台] 查看
    req.SignName = sign_name

    # 模板 ID: 必须填写已审核通过的模板 ID。模板ID可登录 [短信控制台] 查看
    req.TemplateId = template_id
    # 模板参数: 若无模板参数，则设置为空
    req.TemplateParamSet = template_params
    req.PhoneNumberSet = phone_list

    return client.SendSms(req)


def send_message(phone_list: List[str], time1: str, time2: str) -> models.SendSmsResponse:
    """
    批量发送商家接单提醒
    """
    return send_tencent_sms(
        appid='1400647289',
        sign_name='XMU智能点餐',
        template_id='1334610',
        template_params=[str(time1), str(time2)],
        phone_list=phone_list
    )


def send_verification_code(phone: str, code: str, timeout: int = 5):
    """
    发送短信验证码
    """
    return send_tencent_sms(
        appid='1400647289',
        sign_name='XMU智能点餐',
        template_id='1344135',
        template_params=[str(code), str(timeout)],
        phone_list=[str(phone)]
    )
