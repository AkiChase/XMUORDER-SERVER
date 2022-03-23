import re

import execjs
import requests
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .. import dependencies, security
from ..common import SuccessInfo, ErrorInfo
from ..database import Mysql
from ..security import AES

router = APIRouter()


class BindModel(BaseModel):
    """
    绑定信息模版
    """
    id: str
    uid: str
    pw: str
    ts: str


class LoginModel(BaseModel):
    """
    登录信息模版
    """
    uid: str
    ts: str


@router.post("/bind")
async def xmu_bind(data: BindModel, verify=Depends(dependencies.code_verify_aes_depend)):
    """
    通过统一身份认证账号密码绑定用户信息，储存至数据库，并返回基本信息
    """
    session = requests.session()
    session.headers['user-agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
                                    " AppleWebKit/537.36 (KHTML, like Gecko)" \
                                    " Chrome/99.0.4844.74 Safari/537.36"
    try:
        key = 'ord' + data.ts[0:11] + 'er_'
        iv = 're_' + data.ts[0:11] + 'dro'
        account = AES.decrypt_aes(key, iv, en_src=data.id)
        password = AES.decrypt_aes(key, iv, en_src=data.pw)
        openid = AES.decrypt_aes(key, iv, en_src=data.uid)

        # 账号密码登录
        login_by_pw(session, account=account, pw=password)

        # 获取基本信息
        basic_info = get_basic_info(session)

        info = {}
        key_dict = {
            '姓名': 'name', '学号': 'user_id', '学院': 'college', '现在年级': 'grade', '手机': 'phone'
        }
        for item in basic_info:
            if item['title'] in key_dict:
                info[key_dict[item['title']]] = item['initializationValue']['stringValue']

        # 以openid为 key, iv 加密
        key = openid[0:16]
        iv = openid[-16:]
        en_pw = AES.encrypt_aes(key, iv, password)

        info['openid'] = openid
        info['account'] = account
        info['pw'] = en_pw

        # 储存需要的信息到数据库
        store_info(info)

        # 退出登录
        session_logout(session)

        session.close()

        print(f"{info['user_id']}绑定成功！")
        return SuccessInfo('bind success', data={
            'name': info['name'],
            'college': info['college'],
            'grade': info['grade'],
            'user_id': info['user_id']
        }).to_dict()

    except Exception as e:
        print(e)
        session.close()
        raise HTTPException(status_code=400, detail=ErrorInfo('bind failed').to_dict())


@router.post("/login")
async def xmu_login(data: LoginModel, verify=Depends(dependencies.code_verify_aes_depend)):
    """
    通过openid读取数据库，返回用户信息
    """
    try:
        key = 'ord' + data.ts[0:11] + 'er_'
        iv = 're_' + data.ts[0:11] + 'dro'
        openid = AES.decrypt_aes(key, iv, en_src=data.uid)

        data = read_info(openid)
        print(f"{data['user_id']}绑定成功！")
        return SuccessInfo('login success', data=data).to_dict()

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=ErrorInfo('login failed').to_dict())


def read_info(openid: str) -> dict:
    conn = Mysql.connect()
    try:
        sql = "select user_id, name, college, grade from user where openid = %(openid)s;"
        res = Mysql.execute_fetchone(conn, sql, openid=openid)
        return {
            'user_id': res[0],
            'name': res[1],
            'college': res[2],
            'grade': res[3]
        }
    finally:
        conn.close()


def store_info(info: dict) -> None:
    """
    储存用户信息到数据库，若openid或学号存在则更新，否则insert
    :param info: 信息字典
    """
    conn = Mysql.connect()
    try:
        sql = '''
        insert into user (openid, user_id, account, pw, name, college, phone, grade)
        VALUES (%(openid)s, %(user_id)s, %(account)s, %(pw)s, %(name)s, %(college)s, %(phone)s, %(grade)s)
        ON DUPLICATE KEY UPDATE
        user_id=%(user_id)s,
        account=%(account)s, pw=%(pw)s,
        name=%(name)s, college=%(college)s,
        phone=%(phone)s, grade=%(grade)s;'''

        Mysql.execute_fetchall(conn, sql, **info)
    except Exception as e:
        raise Exception(e)
    finally:
        conn.commit()
        conn.close()


def get_basic_info(session: requests.Session) -> dict:
    """
    获取学工系统上的基本信息
    :param session: 已登录统一身份的session
    :return: 所有信息字典
    """

    #  登录学工系统
    url = 'https://ids.xmu.edu.cn/authserver/login?service=https://xmuxg.xmu.edu.cn/login/cas/xmu'
    res = session.get(url, allow_redirects=False)

    # 获取cookie： SAAS_U
    url = res.headers['Location']
    session.get(url, allow_redirects=False)

    # 获取信息
    url = 'https://xmuxg.xmu.edu.cn/api/information/my/infoSettings/STUDENT/1?distributary=owner'
    res = session.get(url)
    return res.json()['data']['components']


def login_by_pw(session: requests.Session, account: str, pw: str) -> requests.Response:
    """
    通过账号密码登录
    :param session: requests.Session
    :param account: 账号
    :param pw: 密码
    :return: 统一身份登录响应
    """
    url = 'https://ids.xmu.edu.cn/authserver/login'

    res = session.get(url, timeout=5)
    assert res.status_code == 200

    info = {}
    for name in ('lt', 'dllt', 'execution', '_eventId', 'rmShown', 'pwdDefaultEncryptSalt'):
        key = 'name' if name != 'pwdDefaultEncryptSalt' else 'id'
        result = re.search(r'{}="{}" value="([\s\S]*?)"'.format(key, name), res.text)
        assert result is not None, 'match failed'
        info[name] = result.group(1)

    with open(r'../lib/encrypt.js', 'r') as f:
        js = f.read()
    ctx = execjs.compile(js)
    password = ctx.call('encryptAES', pw, info['pwdDefaultEncryptSalt'])

    # 登录
    data = {
        'username': account,
        'password': password,
        'lt': info['lt'],
        'dllt': info['dllt'],
        'execution': info['execution'],
        '_eventId': info['_eventId'],
        'rmShown': info['rmShown']
    }

    login_res = session.post(url, data=data)
    assert login_res.status_code == 200
    return login_res


def session_logout(session: requests.Session):
    """
    退出统一身份登录
    :param session:已登录的session
    :return:
    """
    url = 'https://ids.xmu.edu.cn/authserver/logout'
    return session.get(url)
