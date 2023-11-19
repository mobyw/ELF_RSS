from typing import List, NoReturn

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

rss_unsub = Alconna("unsub", Args["name?", str], Args["confirm?", str])
unsub_cmd: type[AlconnaMatcher] = on_alconna(
    rss_unsub,
    aliases={"del", "退订", "取消订阅"},
    rule=to_me(),
    block=True,
)
"""
RSS 退订响应器

命令： unsub [name]

示例： unsub abc
"""


@unsub_cmd.handle()
async def unsub_cmd_permission(event: Event) -> NoReturn:
    """
    RSS 退订命令权限检查

    仅允许超级管理员使用 # TODO: 允许动态配置权限
    """
    user_id = event.get_user_id()
    if user_id not in nonebot_config.superusers:
        await unsub_cmd.finish("你没有权限使用此命令哦")


@unsub_cmd.handle()
async def unsub_cmd_preprocess(matcher: AlconnaMatcher, name: Match[str]) -> NoReturn:
    """
    RSS 退订命令预处理
    """
    if name.available:
        matcher.set_path_arg("name", name.result)


@unsub_cmd.got_path("name", prompt="请输入要退订的订阅名，回复 q 取消")
async def unsub_cmd_param_name(bot: Bot, name: str, target: PlatformTarget = Depends(get_target)) -> NoReturn:
    """
    RSS 退订命令 name 参数获取与检验
    """
    if name == "q":
        await unsub_cmd.finish("已取消")
    if name != "all":
        # 非批量退订 参数检验
        rss = await Rss.get_rss(name, bot.self_id)
        if rss is None:
            await unsub_cmd.reject(f"订阅 {name} 不存在，请重新输入，回复 q 取消")
        if target not in rss.get_targets():
            await unsub_cmd.finish(f"当前位置未订阅 {name}")


@unsub_cmd.handle()
async def unsub_cmd_handle(bot: Bot, name: str, target: PlatformTarget = Depends(get_target)) -> NoReturn:
    """
    RSS 退订命令处理：非批量退订
    """
    if name != "all":
        # 非批量退订 删除订阅目标
        rss = await Rss.get_rss(name, bot.self_id)
        assert rss is not None
        assert target in rss.get_targets()
        # 删除定时任务
        trigger.delete_job(rss)
        # 删除订阅目标
        await rss.delete_target(target)
        if not rss.targets:
            # 订阅目标为空时删除订阅
            await rss.delete()
        elif not rss.stop:
            # 订阅目标不为空且未停止时重新添加定时任务
            await trigger.add_job(rss)
        text = f"已退订 {name}"
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            text = text.replace(".", "．")
        logger.debug(text)
        await unsub_cmd.finish(text)


@unsub_cmd.got_path("confirm", prompt="即将删除所有订阅，回复 y 确认")
async def unsub_cmd_param_confirm(bot: Bot, confirm: str, target: PlatformTarget = Depends(get_target)) -> NoReturn:
    """
    RSS 退订命令处理：批量退订
    """
    if confirm == "y":
        # 批量删除所有订阅
        names: List[str] = []
        for rss in await Rss.get_rss_list(bot.self_id):
            if target in rss.get_targets():
                # 删除定时任务
                trigger.delete_job(rss)
                # 删除订阅目标
                await rss.delete_target(target)
                if not rss.targets:
                    # 订阅目标为空时删除订阅
                    await rss.delete()
                elif not rss.stop:
                    # 订阅目标不为空且未停止时重新添加定时任务
                    await trigger.add_job(rss)
                names.append(rss.name)
        if names:
            text = f"已退订订阅 {', '.join(names)}"
            if bot.self_id in plugin_config.rss_hide_url_bots:
                # 链接特殊处理
                text = text.replace(".", "．")
            logger.debug(text)
            await unsub_cmd.finish(text)
        await unsub_cmd.finish("当前位置没有订阅")
    else:
        await unsub_cmd.finish("已取消")
