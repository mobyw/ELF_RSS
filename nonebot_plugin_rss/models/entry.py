from hashlib import md5

from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import String, Integer, delete, select

from .feed import FeedEntry


class Entry(Model):
    """
    订阅内容
    """

    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    """
    ID
    """
    rss_id: Mapped[int] = mapped_column(Integer)
    """
    订阅 ID
    """
    title: Mapped[str] = mapped_column(String(256), default="")
    """
    标题
    """
    link: Mapped[str] = mapped_column(String(512), default="")
    """
    链接
    """
    published: Mapped[str] = mapped_column(String(64), default="")
    """
    发布时间
    """
    hash: Mapped[str] = mapped_column(String(256), default="")
    """
    指纹
    """

    @staticmethod
    async def check_exist(rss_id: int, entry: FeedEntry) -> bool:
        """
        检查内容是否存在
        """
        hash = md5(f"{entry.title}{entry.link}{entry.published}".encode()).hexdigest()
        async with get_session() as session:
            stmt = select(Entry).where(Entry.rss_id == rss_id, Entry.hash == hash)
            result = await session.execute(stmt)
            return bool(result.first() is not None)

    @staticmethod
    async def add(rss_id: int, entry: FeedEntry) -> bool:
        """
        添加内容
        """
        hash = md5(f"{entry.title}{entry.link}{entry.published}".encode()).hexdigest()
        async with get_session() as session:
            session.add(
                Entry(
                    rss_id=rss_id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    hash=hash,
                )
            )
            await session.commit()
            return True

    @staticmethod
    async def clear(rss_id: int) -> None:
        """
        清空内容
        """
        async with get_session() as session:
            stmt = delete(Entry).where(Entry.rss_id == rss_id)
            await session.execute(stmt)
            await session.commit()
