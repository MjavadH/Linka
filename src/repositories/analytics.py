from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, case, distinct, func, literal, or_, select

from models.broadcast import BroadcastJob
from models.download import Download
from models.enums import BroadcastStatus, ContentType
from models.file import Episode, File, FileVariant, Series
from models.sponsor import Sponsor
from models.subscription import PremiumPlan, Subscription
from models.user import User
from models.user_ban import UserBan
from repositories.base import BaseRepository

ANALYTICS_PAGE_SIZE = 5


@dataclass(frozen=True, slots=True)
class OverviewStatisticsRow:
    total_users: int
    active_users: int
    premium_users: int
    banned_users: int
    total_downloads: int
    downloads_today: int
    downloads_yesterday: int
    downloads_last_7_days: int
    downloads_last_30_days: int
    total_movies: int
    total_series: int
    total_episodes: int
    total_variants: int


@dataclass(frozen=True, slots=True)
class UserStatisticsRow:
    total_users: int
    new_today: int
    new_yesterday: int
    new_last_7_days: int
    new_last_30_days: int
    active_today: int
    active_last_7_days: int
    active_last_30_days: int
    users_with_downloads: int
    users_without_downloads: int


@dataclass(frozen=True, slots=True)
class PremiumPlanStatisticsRow:
    plan_name: str
    active_count: int
    expired_count: int


@dataclass(frozen=True, slots=True)
class PremiumStatisticsRow:
    active_premium_users: int
    expired_premium_users: int
    premium_users_today: int
    premium_users_last_7_days: int
    premium_users_last_30_days: int
    most_popular_plan: str
    plan_statistics: tuple[PremiumPlanStatisticsRow, ...]


@dataclass(frozen=True, slots=True)
class DownloadStatisticsRow:
    total_downloads: int
    downloads_today: int
    downloads_yesterday: int
    downloads_last_7_days: int
    downloads_last_30_days: int
    premium_downloads: int
    free_downloads: int
    average_downloads_per_user: float


@dataclass(frozen=True, slots=True)
class RankingPage:
    items: tuple[Any, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class ContentRankingRow:
    id: int
    title: str
    downloads: int


@dataclass(frozen=True, slots=True)
class VariantRankingRow:
    id: int
    title: str
    quality: str
    downloads: int


@dataclass(frozen=True, slots=True)
class SeriesAnalyticsRow:
    id: int
    title: str
    total_downloads: int
    episode_count: int
    most_downloaded_episode: str
    least_downloaded_episode: str
    average_downloads_per_episode: float


@dataclass(frozen=True, slots=True)
class SponsorRankingRow:
    id: int
    name: str
    verified_users: int
    current_member_count: int | None
    expiration_type: str
    status: str


@dataclass(frozen=True, slots=True)
class BroadcastStatisticsRow:
    total_broadcasts: int
    successful_broadcasts: int
    cancelled_broadcasts: int
    last_broadcast_date: datetime | None
    most_successful_broadcast_id: int | None
    most_successful_broadcast_delivered: int


class AnalyticsRepository(BaseRepository[object]):
    """Optimized read-model queries for admin-only analytics reports."""

    async def overview(self, *, now: datetime, today: datetime, yesterday: datetime, last_7: datetime, last_30: datetime) -> OverviewStatisticsRow:
        return OverviewStatisticsRow(
            total_users=await self._scalar_count(select(func.count(User.id))),
            active_users=await self._scalar_count(select(func.count(User.id)).where(User.last_seen_at >= last_30)),
            premium_users=await self._active_premium_users(now),
            banned_users=await self._banned_users(now),
            total_downloads=await self._downloads_count(),
            downloads_today=await self._downloads_count(Download.created_at >= today),
            downloads_yesterday=await self._downloads_count(Download.created_at >= yesterday, Download.created_at < today),
            downloads_last_7_days=await self._downloads_count(Download.created_at >= last_7),
            downloads_last_30_days=await self._downloads_count(Download.created_at >= last_30),
            total_movies=await self._scalar_count(select(func.count(File.id)).where(File.content_type == ContentType.MOVIE)),
            total_series=await self._scalar_count(select(func.count(Series.id))),
            total_episodes=await self._scalar_count(select(func.count(Episode.id))),
            total_variants=await self._scalar_count(select(func.count(FileVariant.id))),
        )

    async def users(self, *, today: datetime, yesterday: datetime, last_7: datetime, last_30: datetime) -> UserStatisticsRow:
        users_with_downloads = await self._scalar_count(select(func.count(distinct(Download.user_id))))
        total_users = await self._scalar_count(select(func.count(User.id)))
        return UserStatisticsRow(
            total_users=total_users,
            new_today=await self._users_count(User.joined_at >= today),
            new_yesterday=await self._users_count(User.joined_at >= yesterday, User.joined_at < today),
            new_last_7_days=await self._users_count(User.joined_at >= last_7),
            new_last_30_days=await self._users_count(User.joined_at >= last_30),
            active_today=await self._users_count(User.last_seen_at >= today),
            active_last_7_days=await self._users_count(User.last_seen_at >= last_7),
            active_last_30_days=await self._users_count(User.last_seen_at >= last_30),
            users_with_downloads=users_with_downloads,
            users_without_downloads=max(total_users - users_with_downloads, 0),
        )

    async def premium(self, *, now: datetime, today: datetime, last_7: datetime, last_30: datetime) -> PremiumStatisticsRow:
        active_subscribers = select(Subscription.user_id).where(Subscription.is_active.is_(True), Subscription.expires_at > now).distinct()
        expired_subscribers = select(Subscription.user_id).where(or_(Subscription.is_active.is_(False), Subscription.expires_at <= now), Subscription.user_id.not_in(active_subscribers)).distinct()
        popular = await self.session.execute(
            select(PremiumPlan.name, func.count(Subscription.id).label("subscriptions"))
            .join(Subscription, Subscription.plan_id == PremiumPlan.id)
            .group_by(PremiumPlan.id, PremiumPlan.name)
            .order_by(func.count(Subscription.id).desc(), PremiumPlan.name.asc())
            .limit(1)
        )
        plan_rows_result = await self.session.execute(
            select(
                PremiumPlan.name,
                func.coalesce(func.sum(case((and_(Subscription.is_active.is_(True), Subscription.expires_at > now), 1), else_=0)), 0),
                func.coalesce(func.sum(case((or_(Subscription.is_active.is_(False), Subscription.expires_at <= now), 1), else_=0)), 0),
            )
            .outerjoin(Subscription, Subscription.plan_id == PremiumPlan.id)
            .group_by(PremiumPlan.id, PremiumPlan.name)
            .order_by(PremiumPlan.name.asc())
        )
        plan_statistics = tuple(PremiumPlanStatisticsRow(str(name), int(active or 0), int(expired or 0)) for name, active, expired in plan_rows_result.all())
        popular_row = popular.first()
        return PremiumStatisticsRow(
            active_premium_users=await self._scalar_count(select(func.count()).select_from(active_subscribers.subquery())),
            expired_premium_users=await self._scalar_count(select(func.count()).select_from(expired_subscribers.subquery())),
            premium_users_today=await self._subscription_users_since(today),
            premium_users_last_7_days=await self._subscription_users_since(last_7),
            premium_users_last_30_days=await self._subscription_users_since(last_30),
            most_popular_plan=str(popular_row[0]) if popular_row else "—",
            plan_statistics=plan_statistics,
        )

    async def downloads(self, *, today: datetime, yesterday: datetime, last_7: datetime, last_30: datetime) -> DownloadStatisticsRow:
        total_downloads = await self._downloads_count()
        total_users = await self._scalar_count(select(func.count(User.id)))
        return DownloadStatisticsRow(
            total_downloads=total_downloads,
            downloads_today=await self._downloads_count(Download.created_at >= today),
            downloads_yesterday=await self._downloads_count(Download.created_at >= yesterday, Download.created_at < today),
            downloads_last_7_days=await self._downloads_count(Download.created_at >= last_7),
            downloads_last_30_days=await self._downloads_count(Download.created_at >= last_30),
            premium_downloads=await self._downloads_count(Download.is_premium_download.is_(True)),
            free_downloads=await self._downloads_count(Download.is_premium_download.is_(False)),
            average_downloads_per_user=round(total_downloads / total_users, 2) if total_users else 0.0,
        )

    async def top_movies(self, page: int, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        downloads = select(Download.file_id, func.count(Download.id).label("downloads")).group_by(Download.file_id).subquery()
        statement = (
            select(File.id, File.title, func.coalesce(downloads.c.downloads, 0).label("downloads"))
            .outerjoin(downloads, downloads.c.file_id == File.id)
            .where(File.content_type == ContentType.MOVIE)
            .order_by(func.coalesce(downloads.c.downloads, 0).desc(), File.title.asc(), File.id.asc())
        )
        rows = await self._page(statement, page, page_size)
        return RankingPage(tuple(ContentRankingRow(int(row[0]), str(row[1]), int(row[2] or 0)) for row in rows[:page_size]), page, page_size, len(rows) > page_size)

    async def top_series(self, page: int, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        statement = (
            select(Series.id, Series.name, func.count(Download.id).label("downloads"))
            .join(Episode, Episode.series_id == Series.id)
            .join(File, File.id == Episode.file_id)
            .outerjoin(Download, Download.file_id == File.id)
            .group_by(Series.id, Series.name)
            .order_by(func.count(Download.id).desc(), Series.name.asc(), Series.id.asc())
        )
        rows = await self._page(statement, page, page_size)
        return RankingPage(tuple(ContentRankingRow(int(row[0]), str(row[1]), int(row[2] or 0)) for row in rows[:page_size]), page, page_size, len(rows) > page_size)

    async def top_variants(self, page: int, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        title_expr = case((Series.id.is_not(None), Series.name + literal(" - Episode ") + Episode.number), else_=File.title)
        statement = (
            select(FileVariant.id, title_expr.label("title"), FileVariant.quality, func.count(Download.id).label("downloads"))
            .join(File, File.id == FileVariant.file_id)
            .outerjoin(Episode, Episode.id == FileVariant.episode_id)
            .outerjoin(Series, Series.id == Episode.series_id)
            .outerjoin(Download, Download.variant_id == FileVariant.id)
            .group_by(FileVariant.id, FileVariant.quality, File.title, Series.id, Series.name, Episode.number)
            .order_by(func.count(Download.id).desc(), title_expr.asc(), FileVariant.quality.asc(), FileVariant.id.asc())
        )
        rows = await self._page(statement, page, page_size)
        return RankingPage(tuple(VariantRankingRow(int(row[0]), str(row[1]), str(row[2]), int(row[3] or 0)) for row in rows[:page_size]), page, page_size, len(rows) > page_size)

    async def series_analytics(self, page: int, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        episode_downloads = (
            select(Episode.id.label("episode_id"), Episode.series_id, Episode.number, func.count(Download.id).label("downloads"))
            .outerjoin(Download, Download.file_id == Episode.file_id)
            .group_by(Episode.id, Episode.series_id, Episode.number)
            .subquery()
        )
        statement = (
            select(
                Series.id,
                Series.name,
                func.coalesce(func.sum(episode_downloads.c.downloads), 0).label("total_downloads"),
                func.count(episode_downloads.c.episode_id).label("episode_count"),
                func.coalesce(func.avg(episode_downloads.c.downloads), 0).label("average_downloads"),
            )
            .outerjoin(episode_downloads, episode_downloads.c.series_id == Series.id)
            .group_by(Series.id, Series.name)
            .order_by(func.coalesce(func.sum(episode_downloads.c.downloads), 0).desc(), Series.name.asc())
        )
        rows = await self._page(statement, page, page_size)
        items: list[SeriesAnalyticsRow] = []
        for row in rows[:page_size]:
            most = await self._series_episode_extreme(int(row[0]), desc=True)
            least = await self._series_episode_extreme(int(row[0]), desc=False)
            items.append(SeriesAnalyticsRow(int(row[0]), str(row[1]), int(row[2] or 0), int(row[3] or 0), most, least, round(float(row[4] or 0), 2)))
        return RankingPage(tuple(items), page, page_size, len(rows) > page_size)

    async def sponsors(self, page: int, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        statement = (
            select(Sponsor.id, Sponsor.title, Sponsor.sponsor_join_count, Sponsor.current_member_count, Sponsor.expiration_type, Sponsor.is_active)
            .order_by(Sponsor.sponsor_join_count.desc(), Sponsor.title.asc(), Sponsor.id.asc())
        )
        rows = await self._page(statement, page, page_size)
        return RankingPage(tuple(SponsorRankingRow(int(row[0]), str(row[1]), int(row[2] or 0), row[3], str(row[4]), "Active" if row[5] else "Inactive") for row in rows[:page_size]), page, page_size, len(rows) > page_size)

    async def broadcasts(self) -> BroadcastStatisticsRow:
        most_successful = await self.session.execute(
            select(BroadcastJob.id, BroadcastJob.delivered_count)
            .order_by(BroadcastJob.delivered_count.desc(), BroadcastJob.id.desc())
            .limit(1)
        )
        most_row = most_successful.first()
        return BroadcastStatisticsRow(
            total_broadcasts=await self._scalar_count(select(func.count(BroadcastJob.id))),
            successful_broadcasts=await self._scalar_count(select(func.count(BroadcastJob.id)).where(BroadcastJob.status == BroadcastStatus.COMPLETED)),
            cancelled_broadcasts=await self._scalar_count(select(func.count(BroadcastJob.id)).where(BroadcastJob.status == BroadcastStatus.CANCELLED)),
            last_broadcast_date=await self.session.scalar(select(func.max(BroadcastJob.created_at))),
            most_successful_broadcast_id=int(most_row[0]) if most_row else None,
            most_successful_broadcast_delivered=int(most_row[1] or 0) if most_row else 0,
        )

    async def _series_episode_extreme(self, series_id: int, *, desc: bool) -> str:
        downloads = func.count(Download.id)
        order = downloads.desc() if desc else downloads.asc()
        result = await self.session.execute(
            select(Episode.number, downloads.label("downloads"))
            .outerjoin(Download, Download.file_id == Episode.file_id)
            .where(Episode.series_id == series_id)
            .group_by(Episode.id, Episode.number)
            .order_by(order, Episode.number.asc())
            .limit(1)
        )
        row = result.first()
        return f"Episode {row[0]} ({int(row[1] or 0)})" if row else "—"

    async def _page(self, statement: Select[tuple[Any, ...]], page: int, page_size: int) -> list[tuple[Any, ...]]:
        offset = (max(page, 1) - 1) * page_size
        result = await self.session.execute(statement.offset(offset).limit(page_size + 1))
        return list(result.all())

    async def _downloads_count(self, *criteria: Any) -> int:
        statement = select(func.count(Download.id))
        if criteria:
            statement = statement.where(*criteria)
        return await self._scalar_count(statement)

    async def _users_count(self, *criteria: Any) -> int:
        statement = select(func.count(User.id))
        if criteria:
            statement = statement.where(*criteria)
        return await self._scalar_count(statement)

    async def _active_premium_users(self, now: datetime) -> int:
        return await self._scalar_count(select(func.count(distinct(Subscription.user_id))).where(Subscription.is_active.is_(True), Subscription.expires_at > now))

    async def _banned_users(self, now: datetime) -> int:
        return await self._scalar_count(
            select(func.count(distinct(UserBan.user_id))).where(UserBan.is_active.is_(True), or_(UserBan.is_permanent.is_(True), UserBan.banned_until > now))
        )

    async def _subscription_users_since(self, since: datetime) -> int:
        return await self._scalar_count(select(func.count(distinct(Subscription.user_id))).where(Subscription.created_at >= since))

    async def _scalar_count(self, statement: Any) -> int:
        return int(await self.session.scalar(statement) or 0)
