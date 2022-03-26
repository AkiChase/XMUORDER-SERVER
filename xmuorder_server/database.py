import pymysql
from dbutils.pooled_db import PooledDB
import atexit

from .logger import Logger

"""
数据库相关 连接池及部分操作封装
"""

#   当前模块日志
logger: Logger


class Mysql:
    pool: PooledDB  # 数据库连接池

    @classmethod
    def init(cls, database_host: str, database_port: int, database_user: str, database_password: str,
             database_name: str, **ignore):
        global logger
        logger = Logger('数据库模块')

        cls.pool = PooledDB(
            creator=pymysql,  # 使用链接数据库的模块
            maxconnections=10,  # 连接池允许的最大连接数，0和None表示不限制连接数
            mincached=2,  # 初始化时，链接池中至少创建的空闲的链接，0表示不创建
            maxcached=5,  # 链接池中最多闲置的链接，0和None不限制
            maxshared=3,
            # 链接池中最多共享的链接数量，0和None表示全部共享。
            # PS: 无用，因为pymysql和MySQLdb等模块的 threadsafety都为1，永远是所有链接都共享。
            blocking=True,  # 连接池中如果没有可用连接后，是否阻塞等待。True，等待；False，不等待然后报错
            maxusage=1000,  # 一个链接最多被重复使用的次数，None表示无限制
            setsession=[],  # 开始会话前执行的命令列表。
            ping=2,  # ping MySQL服务端，检查是否服务可用。 2 = when a cursor is created
            host=database_host,
            port=database_port,
            user=database_user,
            password=database_password,
            database=database_name,
            charset='utf8'
        )
        logger.info('Mysql连接池已开启')
        #   注册句柄，程序退出时自动断开Mysql连接
        atexit.register(lambda: Mysql.close())

    @classmethod
    def close(cls):
        cls.pool.close()
        logger.info('Mysql连接已断开')

    @classmethod
    def connect(cls) -> pymysql.connections.Connection:
        return cls.pool.connection()

    @staticmethod
    def get_cursor(conn: pymysql.connections.Connection) -> pymysql.cursors.Cursor:
        """
        静态方法：封装获取连接的游标
        :param conn: 连接
        :return: 游标
        """
        return conn.cursor()

    @staticmethod
    def execute_fetchone(conn: pymysql.connections.Connection, sql: str, **params):
        """
        静态方法：封装conn执行sql后返回一条结果。通过params实现预编议，防止注入。
        :param conn: 连接
        :param sql: sql语句
        :param params: sql中占位符对应字典
        :return: 一条结果
        """
        with Mysql.get_cursor(conn) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    @staticmethod
    def execute_fetchmany(conn: pymysql.connections.Connection, sql: str, count: int, **params):
        """
        静态方法：封装conn执行sql后返回count条结果。通过params实现预编议，防止注入。
        :param conn: 连接
        :param sql: sql语句
        :param count: 返回结果数
        :param params: sql中占位符对应字典
        :return: count条结果
        """
        with Mysql.get_cursor(conn) as cur:
            cur.execute(sql, params)
            return cur.fetchmany(count)

    @staticmethod
    def execute_fetchall(conn: pymysql.connections.Connection, sql: str, **params):
        """
        静态方法：封装conn执行sql后返回全部结果。通过params实现预编议，防止注入。
        :param conn: 连接
        :param sql: sql语句
        :param params: sql中占位符对应字典
        :return: 全部结果
        """
        with Mysql.get_cursor(conn) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def execute_only(conn: pymysql.connections.Connection, sql: str, **params) -> None:
        """
        静态方法：封装conn执行sql后返回全部结果。通过params实现预编议，防止注入。
        :param conn: 连接
        :param sql: sql语句
        :param params: sql中占位符对应字典
        :return: 全部结果
        """
        with Mysql.get_cursor(conn) as cur:
            cur.execute(sql, params)
