import asyncio

from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot.drivers import Driver
from nonebot.plugin import PluginMetadata, require, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")
require("nonebot_plugin_saa")

from . import trigger  # noqa: E402
from .models import Rss  # noqa: E402
from .config import ELFConfig  # noqa: E402

VERSION = "3.0.0-alpha.1"

__plugin_meta__ = PluginMetadata(
    name="ELF_RSS",
    description="RSS 订阅插件，订阅源建议选择 RSSHub",
    usage="https://github.com/Quan666/ELF_RSS",
    type="application",
    config=ELFConfig,
    homepage="https://github.com/Quan666/ELF_RSS",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_saa", "nonebot_plugin_alconna"),
    extra={"author": "Quan666 <i@Rori.eMail>", "version": VERSION},
)

driver: Driver = get_driver()


@driver.on_startup
async def startup():
    rss_list = await Rss.get_rss_list()
    if not rss_list:
        message = "首次启动，目前没有订阅，请添加！\n另外，请检查配置文件的内容（详见部署教程）！"
        logger.info(repr(message))
    logger.success("ELF_RSS 订阅器启动成功！")


@driver.on_bot_connect
async def bot_connect(bot: Bot):
    rss_list = await Rss.get_rss_list(bot.self_id)
    if not rss_list:
        message = f"Bot {bot.self_id} 目前没有订阅，请添加！"
        logger.info(repr(message))
    else:
        for rss in rss_list:
            # 创建定时任务
            asyncio.create_task(trigger.add_job(rss)) if not rss.stop else None
        logger.success(f"已为 Bot {bot.self_id} 添加 RSS 更新定时任务！")


@driver.on_bot_disconnect
async def bot_disconnect(bot: Bot):
    rss_list = await Rss.get_rss_list(bot.self_id)
    for rss in rss_list:
        # 创建定时任务
        trigger.delete_job(rss)
    logger.warning(f"Bot {bot.self_id} 断开连接，已删除 RSS 更新定时任务！")


from . import commands as commands  # noqa: E402
