import re
from typing import List, Union, NoReturn, Optional

from nonebot.log import logger
from nonebot.rule import to_me
from nonebot.params import Depends
from nonebot.adapters import Bot, Event
from arclet.alconna import Args, Option, Alconna
from nonebot_plugin_saa import PlatformTarget, get_target
from nonebot_plugin_alconna import Match, Duplication, AlconnaMatcher, AlconnaDuplication, on_alconna

from .. import trigger
from ..models import Rss
from ..config import plugin_config, nonebot_config

rss_mod = Alconna(
    "mod",
    Args["name", str],
    Option("url", Args["url", str]),
    Option("time", Args["time", str]),
    Option("stop", Args["stop", Union[bool, int]]),
    Option("proxy", Args["proxy", Union[bool, int]]),
    Option("op", Args["only_pic", Union[bool, int]]),
    Option("ot", Args["only_title", Union[bool, int]]),
    Option("cp", Args["contains_pic", Union[bool, int]]),
    Option("dp", Args["download_pic", Union[bool, int]]),
    Option("tr", Args["translate", Union[bool, int]]),
    Option("ck", Args["cookie", str]),
    Option("wk", Args["white_keyword", str]),
    Option("bk", Args["black_keyword", str]),
    Option("ft", Args["filters", str]),
    Option("cr", Args["contents_to_remove", str]),
    Option("mi", Args["max_image_number", int]),
    Args["confirm?", str],
)
mod_cmd: type[AlconnaMatcher] = on_alconna(
    rss_mod,
    aliases={"change", "修改订阅"},
    rule=to_me(),
    block=True,
)
"""
RSS 修改订阅响应器

命令： mod [name] [url | time | stop | proxy | op | ot | cp | dp | tr | ck | wk | bk | ft | cr | mi] [value]

示例： mod abc url /example/abc time 10 tr 1 ft link,title,or mi 10

参数：
    name: 订阅名
    url: 订阅链接
    time: 订阅更新时间
    stop: 是否停止订阅
    proxy: 是否使用代理
    op: 仅发送图片
    ot: 仅发送标题
    cp: 仅包含图片
    dp: 下载图片
    tr: 是否开启翻译
    ck: cookie
    wk: 白名单关键词
    bk: 黑名单关键词
    ft: 过滤器
    cr: 内容过滤
    mi: 最大图片数量
    confirm: 确认批量修改

说明：
    超级管理员可修改所有订阅
    非超级管理员可修改私有订阅
    批量修改不允许修改 url
"""


class ModifyResult(Duplication):
    url: Optional[str]
    time: Optional[str]
    cookie: Optional[str]
    white_keyword: Optional[str]
    black_keyword: Optional[str]
    stop: Union[bool, int, None]
    proxy: Union[bool, int, None]
    only_pic: Union[bool, int, None]
    only_title: Union[bool, int, None]
    contains_pic: Union[bool, int, None]
    download_pic: Union[bool, int, None]
    translate: Union[bool, int, None]
    filters: Optional[str]
    contents_to_remove: Optional[str]
    max_image_number: Optional[int]


def rss_modify(rss: Rss, result: ModifyResult) -> Rss:  # noqa: C901
    # 参数 str
    for param in {
        "url",
        "time",
        "cookie",
        "white_keyword",
        "black_keyword",
    }:
        value = getattr(result, param)
        if isinstance(value, str):
            setattr(rss, param, value)
    # 参数 bool
    for param in {
        "stop",
        "proxy",
        "only_pic",
        "only_title",
        "contains_pic",
        "download_pic",
        "translate",
    }:
        value = getattr(result, param)
        if isinstance(value, Union[str, bool]):
            setattr(rss, param, value)
        elif isinstance(value, int):
            setattr(rss, param, bool(value))
    # 参数特殊处理 filters str list
    if isinstance(result.filters, str) and result.filters.strip():
        filters = re.split(r"[,，]", result.filters)
        for r in filters:
            # 只接收 link title image or
            if r not in {"link", "title", "image", "or"}:
                filters.remove(r)
        rss.filters = filters
    # 参数特殊处理 contents_to_remove str list
    if isinstance(result.contents_to_remove, str) and result.contents_to_remove.strip():
        # 逗号分隔
        rss.contents_to_remove = re.split(r"[,，]", result.contents_to_remove)
    # 参数特殊处理 max_image_number int
    if isinstance(result.max_image_number, int):
        # -1 为不限制 所有负数均视为 -1
        rss.max_image_number = result.max_image_number if result.max_image_number >= 0 else -1
    return rss


@mod_cmd.handle()
async def mod_cmd_permission(event: Event) -> NoReturn:
    """
    RSS 修改订阅命令权限检查

    仅允许超级管理员使用 # TODO: 允许动态配置权限
    """
    user_id = event.get_user_id()
    if user_id not in nonebot_config.superusers:
        # 无权限时，直接结束命令
        await mod_cmd.finish("你没有权限使用此命令哦")


@mod_cmd.handle()
async def mod_cmd_preprocess(
    bot: Bot,
    event: Event,
    name: Match[str],
    target: PlatformTarget = Depends(get_target),
) -> NoReturn:
    """
    RSS 修改订阅命令预处理与参数检验
    """
    if not name.available:
        # 无参数时直接结束命令
        await mod_cmd.finish("请在命令后添加订阅名以及要修改的参数")
    if name.result != "all":
        # 非批量修改
        rss = await Rss.get_rss(name.result, bot.self_id)
        if rss is None:
            await mod_cmd.finish(f"订阅 {name.result} 不存在，请检查订阅名")
        if target not in rss.get_targets():
            await mod_cmd.finish(f"当前位置未订阅 {name.result}")
        if len(rss.targets) > 1 and event.get_user_id() not in nonebot_config.superusers:
            await mod_cmd.finish(f"订阅 {name.result} 为公共订阅，仅超级管理员可修改")


@mod_cmd.handle()
async def mod_cmd_handle(
    bot: Bot,
    name: str,
    result: ModifyResult = AlconnaDuplication(ModifyResult),
    target: PlatformTarget = Depends(get_target),
) -> NoReturn:
    """
    RSS 修改订阅命令处理
    """
    if name != "all":
        # 非批量修改 获取订阅
        rss = await Rss.get_rss(name, bot.self_id)
        assert rss is not None
        assert target in rss.get_targets()
        # 删除定时任务
        trigger.delete_job(rss)
        # 修改订阅信息
        rss = rss_modify(rss, result)
        if not rss.stop:
            # 重新添加定时任务
            await trigger.add_job(rss)
        text = f"已修改订阅 {name}\n\n{rss.description()}"
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            text = text.replace(".", "．")
        logger.debug(repr(text))
        await mod_cmd.finish(text)
    else:
        # 批量修改 检查是否修改了 url
        if isinstance(result.url, str):
            await mod_cmd.finish("批量修改不允许修改 url")


@mod_cmd.got_path("confirm", prompt="即将修改所有订阅，回复 y 确认")
async def mod_cmd_param_confirm(
    bot: Bot,
    confirm: str,
    result: ModifyResult = AlconnaDuplication(ModifyResult),
    target: PlatformTarget = Depends(get_target),
) -> NoReturn:
    """
    RSS 修改命令处理：批量修改
    """
    if confirm == "y":
        # 批量修改所有订阅
        names: List[str] = []
        for rss in await Rss.get_rss_list(bot.self_id):
            if target in rss.get_targets() and len(rss.targets) == 1:
                # 删除定时任务
                trigger.delete_job(rss)
                # 修改订阅信息
                rss = rss_modify(rss, result)
                if not rss.stop:
                    # 重新添加定时任务
                    await trigger.add_job(rss)
                names.append(rss.name)
        if names:
            text = f"已修改订阅 {', '.join(names)}"
            if bot.self_id in plugin_config.rss_hide_url_bots:
                # 链接特殊处理
                text = text.replace(".", "．")
            logger.debug(text)
            await mod_cmd.finish(text)
        await mod_cmd.finish("当前位置没有非公共订阅")
    else:
        await mod_cmd.finish("已取消")
