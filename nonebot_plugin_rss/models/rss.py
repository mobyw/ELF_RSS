from typing import Any, List, Optional

from yarl import URL
from nonebot_plugin_saa import PlatformTarget
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import JSON, String, Boolean, Integer, select

from .entry import Entry
from ..config import plugin_config


class Rss(Model):
    """
    RSS 订阅
    """

    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    """
    订阅 ID
    """
    name: Mapped[str] = mapped_column(String(64))
    """
    订阅名
    """
    url: Mapped[str] = mapped_column(String(512))
    """
    订阅地址
    """
    bot_id: Mapped[str] = mapped_column(String(64))
    """
    机器人 ID
    """
    time: Mapped[str] = mapped_column(String(32), default="5")
    """
    更新频率 分钟/次
    """
    targets: Mapped[List[str]] = mapped_column(JSON, default=list)
    """
    订阅目标
    """
    filters: Mapped[List[str]] = mapped_column(JSON, default=list)
    """
    去重模式

    `link`: 链接; `title`: 标题; `image`: 图片; `or`: 修改为或
    """
    proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否使用代理 bool
    """
    translate: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否翻译
    """
    only_title: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否仅发送标题
    """
    only_pic: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否仅发送图片
    """
    contains_pic: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否仅发送含有图片的消息
    """
    download_pic: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否下载图片
    """
    cookie: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    """
    cookie
    """
    white_keyword: Mapped[str] = mapped_column(String(128), default="")
    """
    白名单关键词
    """
    black_keyword: Mapped[str] = mapped_column(String(128), default="")
    """
    黑名单关键词
    """
    max_image_number: Mapped[int] = mapped_column(Integer, default=-1)
    """
    图片数量限制，-1 为不限制
    """
    contents_to_remove: Mapped[List[str]] = mapped_column(JSON, default=list)
    """
    正文待移除内容，支持正则
    """
    etag: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    """
    etag
    """
    last_modified: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    """
    上次更新时间
    """
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    """
    连续抓取失败的次数，超过 100 就停止更新
    """
    stop: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    是否停止更新
    """

    def __init__(self, **kwargs: Any) -> None:
        self.time = "5"
        self.targets = []
        self.filters = []
        self.proxy = False
        self.translate = False
        self.only_title = False
        self.only_pic = False
        self.contains_pic = False
        self.download_pic = False
        self.cookie = None
        self.white_keyword = ""
        self.black_keyword = ""
        self.max_image_number = -1
        self.contents_to_remove = []
        self.etag = None
        self.last_modified = None
        self.error_count = 0
        self.stop = False
        super().__init__(**kwargs)

    def get_url(self, rsshub: str = plugin_config.rss_rsshub) -> str:
        """
        获取完整订阅地址
        """
        if URL(self.url).scheme in {"http", "https"}:
            return self.url
        # 判断地址是否以 / 开头
        if self.url.startswith("/"):
            return rsshub + self.url
        return f"{rsshub}/{self.url}"

    def get_targets(self) -> List[PlatformTarget]:
        """
        获取订阅目标
        """
        return [PlatformTarget.deserialize(i) for i in self.targets]

    async def add_target(self, target: PlatformTarget) -> "Rss":
        """
        添加订阅目标

        同时更新到数据库
        """
        if not self.targets:
            self.targets = [target.json()]
        else:
            targets: List[PlatformTarget] = [PlatformTarget.deserialize(i) for i in self.targets]
            if target in targets:
                return self
            target_serialized: str = target.json()
            self.targets.append(target_serialized)
        await self.update()
        return self

    async def delete_target(self, target: PlatformTarget) -> bool:
        """
        删除订阅目标
        """
        if not self.targets:
            return False
        targets: List[PlatformTarget] = [PlatformTarget.deserialize(i) for i in self.targets]
        if target not in targets:
            return False
        targets.remove(target)
        self.targets = [i.json() for i in targets]
        await self.update()
        return True

    async def set_cookies(self, cookies: Optional[str]) -> None:
        """
        设置 cookies
        """
        self.cookie = cookies
        await self.update()

    async def delete(self) -> None:
        """
        删除订阅
        """
        await Entry.clear(self.id)
        async with get_session() as session:
            await session.delete(self)
            await session.commit()

    async def update(self) -> "Rss":
        """
        更新到数据库
        """
        if (not self.id) and (rss := await Rss.get_rss(self.name, self.bot_id)):
            # 更新数据
            self.id = rss.id
        async with get_session() as session:
            await session.merge(self)
            await session.commit()
            await session.flush()
        return self

    def description(self, privacy: bool = False) -> str:
        """
        格式化输出

        privacy: 是否输出隐私内容 关闭时不输出订阅目标和 cookies
        """

        def _option_str(option: str, value: Any) -> Optional[str]:
            if isinstance(value, bool):
                return f"{option}：是" if value else None
            if isinstance(value, int) and value < 0:
                return None
            return f"{option}：{value}" if value else None

        # 订阅去重模式
        filter_msg: Optional[str] = None
        if self.filters:
            delimiter = " 或 " if "or" in self.filters else " 且 "
            filter_name = {"link": "链接", "title": "标题", "image": "图片"}
            filter_msg = f"{delimiter.join(filter_name[i] for i in self.filters if i != 'or')} 相同时去重"
        # 订阅信息
        result_lines = [
            f"订阅名称：{self.name}",
            f"订阅链接：{self.url}",
            f"更新时间：{self.time}",
            _option_str("订阅目标", self.targets) if privacy else None,
            _option_str("使用代理", self.proxy),
            _option_str("使用翻译", self.translate),
            _option_str("只看标题", self.only_title),
            _option_str("只看图片", self.only_pic),
            _option_str("仅含图片", self.contains_pic),
            _option_str("下载图片", self.download_pic),
            _option_str("白名单词", self.white_keyword),
            _option_str("黑名单词", self.black_keyword),
            _option_str("去重模式", filter_msg),
            _option_str("图片上限", self.max_image_number),
            _option_str("移除内容", self.contents_to_remove),
            _option_str("失败次数", self.error_count),
            _option_str("停止更新", self.stop),
            _option_str("cookies", self.cookie) if privacy else ("已设置 cookies" if self.cookie else None),
        ]
        return "\n".join([i for i in result_lines if i is not None])

    @staticmethod
    async def get_rss_list(bot_id: Optional[str] = None) -> List["Rss"]:
        """
        根据机器人 ID 获取订阅列表
        """
        async with get_session() as session:
            stmt = select(Rss)
            if bot_id is not None:
                stmt = stmt.where(Rss.bot_id == bot_id)
            rss_list = (await session.execute(stmt)).scalars().all()
        return list(rss_list)

    @staticmethod
    async def get_rss(name: str, bot_id: Optional[str] = None) -> Optional["Rss"]:
        """
        根据订阅名获取订阅
        """
        async with get_session() as session:
            stmt = select(Rss).where(Rss.name == name)
            if bot_id is not None:
                stmt = stmt.where(Rss.bot_id == bot_id)
            rss: Optional["Rss"] = (await session.execute(stmt)).scalars().first()
        return rss
