from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import String, Integer, DateTime, or_, and_, delete, select

from .feed import FeedEntry
from ..config import plugin_config


class EntryCache(Model):
    """
    订阅内容去重缓存
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
    link: Mapped[str] = mapped_column(String(256), default="")
    """
    链接
    """
    title: Mapped[str] = mapped_column(String(256), default="")
    """
    标题
    """
    image_hash: Mapped[str] = mapped_column(String(256), default="")
    """
    图片指纹
    """
    time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    """
    发布时间
    """

    @staticmethod
    async def delete_expired() -> None:
        """
        删除过期缓存
        """
        async with get_session() as session:
            stmt = delete(EntryCache).where(
                EntryCache.time < datetime.utcnow() - timedelta(days=plugin_config.rss_cache_expire)
            )
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def check_exist(
        rss_id: int,
        link: Optional[str] = None,
        title: Optional[str] = None,
        image_hash: Optional[str] = None,
        is_or: bool = False,
    ) -> bool:
        """
        检查缓存是否存在
        """
        async with get_session() as session:
            stmt = select(EntryCache).where(EntryCache.rss_id == rss_id)
            clauses = []
            clauses.append(EntryCache.link == link) if link else None
            clauses.append(EntryCache.title == title) if title else None
            clauses.append(EntryCache.image_hash == image_hash) if image_hash else None
            if not clauses:
                return False
            if is_or:
                stmt = stmt.where(or_(*clauses))
            else:
                stmt = stmt.where(and_(*clauses))
            result = await session.execute(stmt)
            return bool(result.first() is not None)

    @staticmethod
    async def add(rss_id: int, entry: FeedEntry) -> bool:
        """
        添加缓存
        """
        async with get_session() as session:
            session.add(
                EntryCache(
                    rss_id=rss_id,
                    link=entry.link,
                    title=entry.title,
                    image_hash=entry.image_hash,
                )
            )
            await session.commit()
            return True
