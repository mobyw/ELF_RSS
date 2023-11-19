from typing import NoReturn

from nonebot.log import logger
from nonebot.rule import to_me
from nonebot.params import Depends
from nonebot.adapters import Bot, Event
from arclet.alconna import Args, Alconna
from nonebot_plugin_saa import PlatformTarget, get_target
from nonebot_plugin_alconna import Match, AlconnaMatcher, on_alconna

from .. import trigger
from ..models import Rss
from ..config import plugin_config, nonebot_config

rss_sub = Alconna("sub", Args["name?", str], Args["url?", str])
sub_cmd: type[AlconnaMatcher] = on_alconna(
    rss_sub,
    aliases={"add", "订阅", "添加订阅"},
    rule=to_me(),
    block=True,
)
"""
RSS 订阅响应器

命令： sub [name] [url]

示例： sub abc /example/abc
"""


@sub_cmd.handle()
async def sub_cmd_permission(event: Event) -> NoReturn:
    """
    RSS 订阅命令权限检查

    仅允许超级管理员使用 # TODO: 允许动态配置权限
    """
    user_id = event.get_user_id()
    if user_id not in nonebot_config.superusers:
        # 无权限时，直接结束命令
        await sub_cmd.finish("你没有权限使用此命令哦")


@sub_cmd.handle()
async def sub_cmd_preprocess(matcher: AlconnaMatcher, name: Match[str], url: Match[str]) -> NoReturn:
    """
    RSS 订阅命令预处理
    """
    if name.available:
        matcher.set_path_arg("name", name.result)
    if url.available:
        matcher.set_path_arg("url", url.result)


@sub_cmd.got_path("name", prompt="请输入订阅名，回复 q 取消")
async def sub_cmd_param_name(bot: Bot, event: Event, matcher: AlconnaMatcher, name: str) -> NoReturn:
    """
    RSS 订阅命令 name 参数获取与检验
    """
    if name == "q":
        await sub_cmd.finish("已取消")
    if name in {"all"}:
        # 保留关键字
        await sub_cmd.reject(f"名称 {name} 不可用，请重新输入，回复 q 取消")
    # 全局名称禁止重复
    rss = await Rss.get_rss(name)
    if rss is not None:
        if event.get_user_id() not in nonebot_config.superusers:
            # 名称已被占用 禁止非超级管理员操作
            await sub_cmd.reject(f"名称 {name} 已被占用，请重新输入，回复 q 取消")
        elif rss.bot_id != bot.self_id:
            # 名称已被其他机器人占用 无法添加订阅目标
            await sub_cmd.finish(f"订阅 {name} 不在当前机器人中")
        else:
            # 订阅在当前机器人中
            # 超级管理员可直接添加订阅目标 忽略链接参数
            matcher.set_path_arg("url", "")


@sub_cmd.got_path("url", prompt="请输入订阅链接，回复 q 取消")
async def sub_cmd_param_url(url: str) -> NoReturn:
    """
    RSS 订阅命令 url 参数获取与检验
    """
    if url == "q":
        await sub_cmd.finish("已取消")
    # TODO: 检验 url 有效性


@sub_cmd.handle()
async def sub_cmd_handle(bot: Bot, name: str, url: str, target: PlatformTarget = Depends(get_target)) -> NoReturn:
    """
    RSS 订阅命令处理
    """
    # 获取可能存在的订阅 超级管理员可直接添加订阅目标
    # 全局名称禁止重复
    rss = await Rss.get_rss(name)
    if rss is None:
        # 订阅不存在时，创建订阅
        rss = Rss(name=name, url=url, bot_id=bot.self_id)
    else:
        # 订阅存在时，检查是否已订阅
        trigger.delete_job(rss)
    # 添加订阅目标
    await rss.add_target(target=target)
    # 添加定时任务
    await trigger.add_job(rss)
    text = f"已添加订阅 {rss.name}，链接为 {rss.url}"
    if bot.self_id in plugin_config.rss_hide_url_bots:
        # 链接特殊处理
        text = text.replace(".", "．")
    logger.debug(text)
    await sub_cmd.send(text)
    await sub_cmd.finish()
