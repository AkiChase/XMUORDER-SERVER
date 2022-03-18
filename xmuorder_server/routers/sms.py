from typing import Optional, Set, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.sms.v20210111 import sms_client, models

from .. import dependencies
from ..config import GlobalSettings
from ..database import Mysql

router = APIRouter()


class SendSmsModel(BaseModel):
    """
    发送信息模板
    """
    cID_list: Set[str]
    time1: Optional[str] = 3
    time2: Optional[str] = 10


@router.post("/send")
async def send_sms(item: SendSmsModel, verify=Depends(dependencies.code_verify_depend)):
    conn = Mysql.connect()

    cid_list = [f"'{x}'" for x in item.cID_list]
    for x in cid_list:
        if x.find(' ') > -1:
            raise HTTPException(status_code=400, detail="cid_list invalid")

    #   过滤出需要发送的电话号码
    sql = f'''
    select c.cID, p.phone
    from canteen c
             left join phone p on c.cID = p.cID
    where c.cID in {f"({','.join(cid_list)})"};
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
    return send_message(list(phone_list), time1=item.time1, time2=item.time2)


def send_message(phone_list: List[str], time1: str, time2: str) -> models.SendSmsResponse:
    """
    使用模板发送商家及时处理订单短信提醒
    :param phone_list: 号码列表，注意每个号码+86
    :param time1: 已超过{1}分钟未处理
    :param time2: 超过{2}分钟未处理，系统将为您自动拒单
    :return:
    """
    try:
        settings = GlobalSettings.get()
        # 实例化一个认证对象，入参需要传入腾讯云账户密钥对secretId，secretKey。
        cred = credential.Credential(settings.secret_id, settings.secret_key)

        # 实例化要请求产品(以sms为例)的client对象 第二个参数为地域
        client = sms_client.SmsClient(cred, "ap-guangzhou")

        # 实例化一个请求对象，根据调用的接口和实际情况，可以进一步设置请求参数
        req = models.SendSmsRequest()

        # 短信应用ID: 短信SdkAppId在 [短信控制台] 添加应用后生成的实际SdkAppId，示例如1400006666
        req.SmsSdkAppId = "1400647289"
        # 短信签名内容: 使用 UTF-8 编码，必须填写已审核通过的签名，签名信息可登录 [短信控制台] 查看
        req.SignName = "XMU智能点餐"

        # 模板 ID: 必须填写已审核通过的模板 ID。模板ID可登录 [短信控制台] 查看
        req.TemplateId = "1334610"
        # 模板参数: 若无模板参数，则设置为空
        req.TemplateParamSet = [time1, time2]
        req.PhoneNumberSet = phone_list

        return client.SendSms(req)

    except TencentCloudSDKException as err:
        print('错误信息', err)
        raise HTTPException(status_code=400, detail="Message sending failed")
