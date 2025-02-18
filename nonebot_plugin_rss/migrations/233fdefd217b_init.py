"""init

迁移 ID: 233fdefd217b
父迁移:
创建时间: 2023-11-19 19:37:36.015139

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "233fdefd217b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "nonebot_plugin_rss_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rss_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("link", sa.String(length=512), nullable=False),
        sa.Column("published", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nonebot_plugin_rss_entry")),
        info={"bind_key": "nonebot_plugin_rss"},
    )
    op.create_table(
        "nonebot_plugin_rss_entrycache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rss_id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("image_hash", sa.String(length=256), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nonebot_plugin_rss_entrycache")),
        info={"bind_key": "nonebot_plugin_rss"},
    )
    op.create_table(
        "nonebot_plugin_rss_rss",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("time", sa.String(length=32), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("proxy", sa.Boolean(), nullable=False),
        sa.Column("translate", sa.Boolean(), nullable=False),
        sa.Column("only_title", sa.Boolean(), nullable=False),
        sa.Column("only_pic", sa.Boolean(), nullable=False),
        sa.Column("contains_pic", sa.Boolean(), nullable=False),
        sa.Column("download_pic", sa.Boolean(), nullable=False),
        sa.Column("cookie", sa.String(length=512), nullable=True),
        sa.Column("white_keyword", sa.String(length=128), nullable=False),
        sa.Column("black_keyword", sa.String(length=128), nullable=False),
        sa.Column("max_image_number", sa.Integer(), nullable=False),
        sa.Column("contents_to_remove", sa.JSON(), nullable=False),
        sa.Column("etag", sa.String(length=64), nullable=True),
        sa.Column("last_modified", sa.String(length=64), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("stop", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nonebot_plugin_rss_rss")),
        info={"bind_key": "nonebot_plugin_rss"},
    )
    # ### end Alembic commands ###


def downgrade(name: str = "") -> None:
    if name:
        return
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("nonebot_plugin_rss_rss")
    op.drop_table("nonebot_plugin_rss_entrycache")
    op.drop_table("nonebot_plugin_rss_entry")
    # ### end Alembic commands ###
