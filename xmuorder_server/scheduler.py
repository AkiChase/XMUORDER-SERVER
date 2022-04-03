import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from .database import Mysql
from .logger import Logger
from .weixin.database import UpdateDataBase

#   当前模块日志
logger: Logger


class Scheduler:
    """
    AsyncIOScheduler 封装
    """
    scheduler: AsyncIOScheduler
    job_dict: dict = {}

    @classmethod
    def init(cls):
        cls.scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')
        cls.scheduler.start()
        global logger
        logger = Logger('定时任务模块')
        logger.info('服务已开启')

        # 同步数据库任务
        Scheduler.add(Task.refresh_database_task, job_name='同步数据库',
                      trigger='cron', minute="0", second='0')

    @classmethod
    def add(cls, func: callable, job_name: str, **kwargs):
        """
        添加任务，并保存到 job_dict
        :param func: 任务执行函数
        :param job_name: 任务名称，对应job_dict的key
        :param kwargs: 其他传入add_job的参数
        """
        if job_name in cls.job_dict:
            raise Exception(f"the job with name '{job_name}' already exists")

        #   附加job_name参数
        if 'kwargs' not in kwargs:
            kwargs['kwargs'] = {'job_name': job_name}
        elif 'job_name' not in kwargs['kwargs']:
            kwargs['kwargs']['job_name'] = job_name

        cls.job_dict[job_name] = cls.scheduler.add_job(func=func, **kwargs)
        logger.info(f'定时任务[{job_name}]已添加, 当前任务数量:{len(cls.job_dict)}')

    @classmethod
    def remove(cls, job_name: str):
        """
        移除任务，同时删除 job_dict 中键值对
        """
        if job_name not in cls.job_dict:
            raise Exception(f"the job with name '{job_name}' doesn't exist")
        job: Job = cls.job_dict[job_name]
        job.remove()
        del cls.job_dict[job_name]
        logger.info(f'定时任务[{job_name}]已移除, 当前任务数量:{len(cls.job_dict)}')


class Task:
    @staticmethod
    def clear_phone_verification_task(job_name: str):
        """
        定时任务，清理过期验证码，重置剩余验证码次数
        """
        try:
            sql1 = 'DELETE FROM phone_verification WHERE NOW() > expiration;'
            sql2 = 'UPDATE phone_verification SET sendTimes = 0 WHERE sendTimes!=0;'
            with Mysql.connect() as conn:
                Mysql.execute_only(conn, sql1)
                Mysql.execute_only(conn, sql2)
                conn.commit()
            logger.success(f'定时任务[{job_name}]已完成')
        except Exception as e:
            logger.error(f'定时任务[{job_name}]发生错误:{e}')

    @staticmethod
    def refresh_database_task(job_name: str):
        """
        定时任务 通过获取微信数据库同步本地mysql数据库
        """
        try:
            UpdateDataBase.update_canteen_table()
            logger.success(f'定时任务[{job_name}]已完成')
        except Exception as e:
            logger.error(f'定时任务[{job_name}]发生错误:{e}')
