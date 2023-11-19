from typing import List, NoReturn

from nonebot.log import logger
from nonebot.rule import to_me
from nonebot.params import Depends
from nonebot.adapters import Bot, Event
from arclet.alconna import Args, Alconna
from nonebot_plugin_saa import PlatformTarget, get_target
from nonebot_plugin_alconna import Match, AlconnaMatcher, on_alconna

from ..models import Rss
from ..config import plugin_config, nonebot_config

rss_view = Alconna("view", Args["name?", str], Args["privacy?", bool, False])
view_cmd: type[AlconnaMatcher] = on_alconna(
    rss_view,
    aliases={"show", "查看订阅"},
    rule=to_me(),
    block=True,
)
"""
RSS 查看订阅响应器

命令： view [name]

示例： view abc

参数：
    name: 订阅名
    privacy: 是否展示隐私信息

说明：
    仅超级管理员可查看隐私信息
    仅超级管理员可查看其他目标的订阅
"""


@view_cmd.handle()
async def view_cmd_permission(event: Event) -> None:
    """
    RSS 查看命令权限检查

    仅允许超级管理员使用 # TODO: 允许动态配置权限
    """
    user_id = event.get_user_id()
    if user_id not in nonebot_config.superusers:
        await view_cmd.finish("你没有权限使用此命令哦")


@view_cmd.handle()
async def view_cmd_preprocess(
    event: Event, matcher: AlconnaMatcher, name: Match[str], privacy: Match[bool]
) -> NoReturn:
    """
    RSS 查看命令预处理
    """
    if name.available:
        matcher.set_path_arg("name", name.result)
    if privacy.available and event.get_user_id() in nonebot_config.superusers:
        matcher.set_path_arg("privacy", privacy.result)
    else:
        matcher.set_path_arg("privacy", False)


@view_cmd.got_path("name", prompt="请输入要查看的订阅名，回复 q 取消")
async def view_cmd_param_name(
    bot: Bot, name: str, privacy: bool, target: PlatformTarget = Depends(get_target)
) -> NoReturn:
    """
    RSS 查看命令 name 参数获取与检验
    """
    if name == "q":
        await view_cmd.finish("已取消")
    if name != "all":
        # 非批量查看 参数检验
        rss = await Rss.get_rss(name, bot.self_id)
        if rss is None:
            await view_cmd.reject(f"订阅 {name} 不存在，请重新输入，回复 q 取消")
        if target not in rss.get_targets() and not privacy:
            await view_cmd.finish(f"当前位置未订阅 {name}")


@view_cmd.handle()
async def view_cmd_handle(bot: Bot, name: str, privacy: bool, target: PlatformTarget = Depends(get_target)) -> NoReturn:
    """
    RSS 查看命令处理
    """
    if name != "all":
        # 非批量查看
        rss = await Rss.get_rss(name, bot.self_id)
        assert rss is not None
        text = rss.description(privacy)
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            text = text.replace(".", "．")
        logger.debug(repr(text))
        await view_cmd.finish(text)
    else:
        # 批量查看
        rss_list: List[Rss] = await Rss.get_rss_list(bot.self_id)
        text = "\n".join([f"{rss.name}: {rss.url}" for rss in rss_list if target in rss.get_targets() or privacy])
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            text = text.replace(".", "．")
        text = text if text else "当前位置无订阅"
        logger.debug(repr(text))
        await view_cmd.finish(text)
