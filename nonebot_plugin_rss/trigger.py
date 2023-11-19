import re
import asyncio

from nonebot.log import logger
from async_timeout import timeout
from nonebot_plugin_apscheduler import scheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

from . import executor
from .models import Rss


async def check_update(rss: Rss):
    """
    检测指定 RSS 更新
    """
    logger.debug(f"{rss.name} 检查更新")
    try:
        wait_for = 5 * 60 if re.search(r"[_*/,-]", rss.time) else int(rss.time) * 60
        async with timeout(wait_for):
            await executor.start(rss)
    except asyncio.TimeoutError:
        logger.error(f"{rss.name} 检查更新超时，结束此次任务!")


def delete_job(rss: Rss) -> None:
    """
    删除指定 RSS 的定时任务
    """
    if scheduler.get_job(f"RSS_{rss.name}"):
        scheduler.remove_job(f"RSS_{rss.name}")
        logger.debug(f"定时任务 RSS_{rss.name} 删除成功")


async def add_job(rss: Rss) -> None:
    """
    添加指定 RSS 的定时任务

    添加后立即执行一次
    """
    delete_job(rss)
    if rss.targets:
        _add_job(rss)
        # 后台执行检查更新
        asyncio.create_task(check_update(rss))


def _add_job(rss: Rss) -> None:
    """
    添加指定 RSS 的定时任务
    """
    if re.search(r"[_*/,-]", rss.time):
        # 处理 cron 定时任务
        _add_cron_job(rss)
        return
    # {rss.time} 分钟/次 触发器
    trigger = IntervalTrigger(minutes=int(rss.time), jitter=10)
    # 添加任务
    scheduler.add_job(
        func=check_update,  # 定时任务
        trigger=trigger,  # 触发器
        args=(rss,),  # 参数列表
        id=f"RSS_{rss.name}",  # 任务 ID
        misfire_grace_time=30,  # 允许的误差时间
        max_instances=1,  # 最大并发
        default=ThreadPoolExecutor(64),  # 最大线程
        processpool=ProcessPoolExecutor(8),  # 最大进程
        coalesce=True,  # 合并所有错过的 Job
    )
    logger.debug(f"定时任务 RSS_{rss.name} 添加成功")


# cron 表达式
# https://www.runoob.com/linux/linux-comm-crontab.html


def _add_cron_job(rss: Rss) -> None:
    """
    添加指定 RSS 的 cron 定时任务
    """
    cron = rss.time.split("_")
    time = ["*/5", "*", "*", "*", "*"]
    for index, value in enumerate(cron):
        if value:
            time[index] = value
    try:
        # 制作一个触发器
        trigger = CronTrigger(
            minute=time[0],
            hour=time[1],
            day=time[2],
            month=time[3],
            day_of_week=time[4],
        )
    except Exception:
        logger.exception(f"创建定时器错误！cron: {time}")
        return
    # 添加任务
    scheduler.add_job(
        func=check_update,  # 定时任务
        trigger=trigger,  # 触发器
        args=(rss,),  # 参数列表
        id=f"RSS_{rss.name}",  # 任务 ID
        misfire_grace_time=30,  # 允许的误差时间
        max_instances=1,  # 最大并发
        default=ThreadPoolExecutor(64),  # 最大线程
        processpool=ProcessPoolExecutor(8),  # 最大进程
        coalesce=True,  # 合并所有错过的 Job
    )
    logger.debug(f"定时任务 RSS_{rss.name} 添加成功")
