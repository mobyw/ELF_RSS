from nonebot.log import logger
from nonebot import require, get_driver
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_datastore")

from .config import ELFConfig  # noqa: E402

VERSION = "2.6.21"

__plugin_meta__ = PluginMetadata(
    name="ELF_RSS",
    description="RSS 订阅插件，订阅源建议选择 RSSHub",
    usage="https://github.com/Quan666/ELF_RSS",
    type="application",
    config=ELFConfig,
    homepage="https://github.com/Quan666/ELF_RSS",
    supported_adapters=None,
    extra={"author": "Quan666 <i@Rori.eMail>", "version": VERSION},
)

driver = get_driver()


@driver.on_startup
async def startup():
    logger.info("ELF_RSS 订阅器启动成功！")
