from apscheduler.schedulers.asyncio import AsyncIOScheduler


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

        cls.job_dict[job_name] = cls.scheduler.add_job(func=func, **kwargs)
