from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from .logger import Logger

#   默认日志
default_logger: Logger


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
        global default_logger
        default_logger = Logger.get_logger('默认日志')
        default_logger.info('定时任务服务已开启')

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
        default_logger.info(f'定时任务[{job_name}]已添加, 当前任务数量:{len(cls.job_dict)}')

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
        default_logger.info(f'定时任务[{job_name}]已移除, 当前任务数量:{len(cls.job_dict)}')
