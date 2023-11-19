import re
from copy import deepcopy
from inspect import signature
from typing import Any, Dict, List, Union, Callable, Optional, TypedDict

from nonebot_plugin_saa import MessageFactory, MessageSegmentFactory

from ..utils import partition_list
from ..models import Rss, FeedEntry, FeedParser, FeedChannel


class ParseState(TypedDict):
    """
    解析上下文信息
    """

    title: str
    """
    发送消息标题
    """
    messages: List[Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory]]]
    """
    发送消息列表
    """
    feed: FeedChannel
    """
    RSS 信息列表
    """
    entries: List[FeedEntry]
    """
    原始 RSS 推送列表
    """
    new_data: List[FeedEntry]
    """
    新增 RSS 推送列表
    """
    filtered: List[FeedEntry]
    """
    过滤后 RSS 推送列表
    """
    message: Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory], None]
    """
    消息构造
    """
    text: str
    """
    文本构造
    """
    stop: bool
    """
    是否停止解析
    """


class ParseItem:
    """
    解析器类

    订阅器启动的时候将解析器注册到 RSS 实例，避免每次推送时再匹配
    """

    def __init__(
        self,
        func: Callable[..., Any],
        rex: str = "(.*)",
        priority: int = 10,
        block: bool = False,
    ):
        self.func: Callable[..., Any] = func
        """
        解析函数
        """
        self.rex: str = rex
        """
        订阅地址匹配正则表达式

        默认为 `(.*)`，即匹配所有订阅地址
        """
        self.priority: int = priority
        """
        优先级，数字越小优先级越高

        优先级相同时，会抛弃默认处理方式
        """
        self.block: bool = block
        """
        是否阻止执行之后的处理，默认不阻止

        抛弃默认处理方式: block==True & priority<10
        """


def _sort(_list: List[ParseItem]) -> List[ParseItem]:
    """
    对解析器进行排序
    """
    _list.sort(key=lambda x: x.priority)
    return _list


class ParseBase:
    before_handler: List[ParseItem] = []
    """
    前置处理器
    """

    handler: Dict[str, List[ParseItem]] = {
        "title": [],
        "summary": [],
        "picture": [],
        "source": [],
        "date": [],
    }
    """
    处理器
    """

    after_handler: List[ParseItem] = []
    """
    后置处理器
    """

    @classmethod
    def append_handler(
        cls,
        parsing_type: str,
        rex: str = "(.*)",
        priority: int = 10,
        block: bool = False,
    ) -> Callable[..., Any]:
        """
        装饰一个方法，作为将其一个处理器
        """

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cls.handler[parsing_type].append(ParseItem(func, rex, priority, block))
            cls.handler.update({parsing_type: _sort(cls.handler[parsing_type])})
            return func

        return _decorator

    @classmethod
    def append_before_handler(cls, rex: str = "(.*)", priority: int = 10, block: bool = False) -> Callable[..., Any]:
        """
        装饰一个方法，作为将其一个前置处理器
        """

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cls.before_handler.append(ParseItem(func, rex, priority, block))
            cls.before_handler = _sort(cls.before_handler)
            return func

        return _decorator

    @classmethod
    def append_after_handler(cls, rex: str = "(.*)", priority: int = 10, block: bool = False) -> Callable[..., Any]:
        """
        装饰一个方法，作为将其一个后置处理器
        """

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cls.after_handler.append(ParseItem(func, rex, priority, block))
            cls.after_handler = _sort(cls.after_handler)
            return func

        return _decorator


def _handler_filter(_handler_list: List[ParseItem], _url: str) -> List[ParseItem]:
    """
    对处理器进行过滤
    """
    _result = [h for h in _handler_list if re.search(h.rex, _url)]
    # 删除优先级相同时默认的处理器
    _delete = [(h.func.__name__, "(.*)", h.priority) for h in _result if h.rex != "(.*)"]
    _result = [h for h in _result if (h.func.__name__, h.rex, h.priority) not in _delete]
    return _result


async def _run_handlers(
    handlers: List[ParseItem],
    rss: Rss,
    state: ParseState,
    entry: Optional[FeedEntry] = None,
) -> ParseState:
    """
    执行处理器
    """
    for handler in handlers:
        kwargs = {
            "rss": rss,
            "state": state,
            "entry": entry,
        }
        handler_params = signature(handler.func).parameters
        handler_kwargs = {k: v for k, v in kwargs.items() if k in handler_params}
        state = await handler.func(**handler_kwargs)
        if handler.block or state["stop"]:
            break
    return state


class ParseRss:
    """
    解析实例
    """

    rss: Rss
    """
    RSS 订阅实例
    """

    def __init__(self, rss: Rss):
        self.rss: Rss = rss

        # 对处理器进行过滤
        self.before_handler: List[ParseItem] = _handler_filter(ParseBase.before_handler, self.rss.get_url())
        self.handler: Dict[str, List[ParseItem]] = {}
        for k, v in ParseBase.handler.items():
            self.handler[k] = _handler_filter(v, self.rss.get_url())
        self.after_handler: List[ParseItem] = _handler_filter(ParseBase.after_handler, self.rss.get_url())

    async def start(self, model: FeedParser) -> None:
        """
        开始解析

        参数:
            name: 订阅名称
            model: RSS 信息
        """
        # 初始化上下文状态
        state: ParseState = {
            "feed": model.feed,
            "entries": model.entries,
            "title": "",
            "messages": [],
            "new_data": [],
            "filtered": [],
            "message": None,
            "text": "",
            "stop": False,
        }
        # 运行前置处理
        state = await _run_handlers(self.before_handler, self.rss, state)
        state["title"] = f"✨ ⌈{model.feed.title}⌋ 更新了!"
        if new_data := state["new_data"]:
            # 新增数据逐条处理
            for entries in partition_list(new_data, 10):
                # 每次最多处理 10 条数据
                for entry in entries:
                    # 处理一条数据
                    for handler_list in self.handler.values():
                        # 依次运行处理函数
                        state = await _run_handlers(handler_list, self.rss, state, entry=entry)
                    if state["message"] is not None:
                        state["messages"].append(deepcopy(state["message"]))
                        state["message"] = None
                # 运行后置处理 发送消息与写入缓存
                await _run_handlers(self.after_handler, self.rss, state)
                state["messages"] = []
        else:
            # 无新推送 直接运行后置处理
            await _run_handlers(self.after_handler, self.rss, state)
