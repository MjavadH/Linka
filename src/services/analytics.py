from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, TypeVar, cast

from repositories.analytics import (
    ANALYTICS_PAGE_SIZE,
    BroadcastStatisticsRow,
    ContentRankingRow,
    DownloadStatisticsRow,
    OverviewStatisticsRow,
    PremiumStatisticsRow,
    RankingPage,
    SeriesAnalyticsRow,
    SponsorRankingRow,
    UserStatisticsRow,
    VariantRankingRow,
)

ReportT = TypeVar("ReportT")
CACHE_TTL_SECONDS = 60



@dataclass(frozen=True, slots=True)
class AnalyticsTimeWindows:
    now: datetime
    today: datetime
    yesterday: datetime
    last_7_days: datetime
    last_30_days: datetime


def build_time_windows(now: datetime | None = None) -> AnalyticsTimeWindows:
    moment = now or datetime.now(UTC)
    today = datetime.combine(moment.date(), time.min, tzinfo=moment.tzinfo or UTC)
    return AnalyticsTimeWindows(
        now=moment,
        today=today,
        yesterday=today - timedelta(days=1),
        last_7_days=moment - timedelta(days=7),
        last_30_days=moment - timedelta(days=30),
    )


class ReportCache:
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[datetime, object]] = {}

    async def get(self, key: str, loader: Callable[[], Awaitable[ReportT]], *, now: datetime | None = None) -> ReportT:
        moment = now or datetime.now(UTC)
        cached = self._items.get(key)
        if cached and (moment - cached[0]).total_seconds() < self.ttl_seconds:
            return cast(ReportT, cached[1])
        value = await loader()
        self._items[key] = (moment, value)
        return value

    def clear(self) -> None:
        self._items.clear()


analytics_cache = ReportCache()


class AnalyticsReportService:
    """Application service for admin analytics reports.

    The service returns typed report objects only. Presentation and future CSV/Excel/PDF
    exporters can format these objects without re-running database queries.
    """

    def __init__(self, repository: Any, cache: ReportCache = analytics_cache) -> None:
        self.repository = repository
        self.cache = cache

    async def overview(self) -> OverviewStatisticsRow:
        windows = build_time_windows()
        return cast(OverviewStatisticsRow, await self.cache.get(
            "overview",
            lambda: self.repository.overview(
                now=windows.now,
                today=windows.today,
                yesterday=windows.yesterday,
                last_7=windows.last_7_days,
                last_30=windows.last_30_days,
            ),
        ))

    async def users(self) -> UserStatisticsRow:
        windows = build_time_windows()
        return cast(UserStatisticsRow, await self.cache.get(
            "users",
            lambda: self.repository.users(
                today=windows.today,
                yesterday=windows.yesterday,
                last_7=windows.last_7_days,
                last_30=windows.last_30_days,
            ),
        ))

    async def premium(self) -> PremiumStatisticsRow:
        windows = build_time_windows()
        return cast(PremiumStatisticsRow, await self.cache.get(
            "premium",
            lambda: self.repository.premium(
                now=windows.now,
                today=windows.today,
                last_7=windows.last_7_days,
                last_30=windows.last_30_days,
            ),
        ))

    async def downloads(self) -> DownloadStatisticsRow:
        windows = build_time_windows()
        return cast(DownloadStatisticsRow, await self.cache.get(
            "downloads",
            lambda: self.repository.downloads(
                today=windows.today,
                yesterday=windows.yesterday,
                last_7=windows.last_7_days,
                last_30=windows.last_30_days,
            ),
        ))

    async def top_movies(self, page: int = 1, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        return cast(RankingPage, await self.cache.get(f"top_movies:{page}:{page_size}", lambda: self.repository.top_movies(page, page_size)))

    async def top_series(self, page: int = 1, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        return cast(RankingPage, await self.cache.get(f"top_series:{page}:{page_size}", lambda: self.repository.top_series(page, page_size)))

    async def top_variants(self, page: int = 1, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        return cast(RankingPage, await self.cache.get(f"top_variants:{page}:{page_size}", lambda: self.repository.top_variants(page, page_size)))

    async def series_analytics(self, page: int = 1, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        return cast(RankingPage, await self.cache.get(f"series_analytics:{page}:{page_size}", lambda: self.repository.series_analytics(page, page_size)))

    async def sponsors(self, page: int = 1, page_size: int = ANALYTICS_PAGE_SIZE) -> RankingPage:
        return cast(RankingPage, await self.cache.get(f"sponsors:{page}:{page_size}", lambda: self.repository.sponsors(page, page_size)))

    async def broadcasts(self) -> BroadcastStatisticsRow:
        return cast(BroadcastStatisticsRow, await self.cache.get("broadcasts", self.repository.broadcasts))


class AnalyticsExportPreparationService:
    """Stable extension point for future analytics exports.

    CSV, Excel, and PDF exporters should depend on AnalyticsReportService and format
    its typed report objects. No export format is implemented yet by design.
    """

    supported_future_formats = ("csv", "excel", "pdf")


__all__ = [
    "AnalyticsExportPreparationService",
    "AnalyticsReportService",
    "AnalyticsTimeWindows",
    "BroadcastStatisticsRow",
    "ContentRankingRow",
    "DownloadStatisticsRow",
    "OverviewStatisticsRow",
    "PremiumStatisticsRow",
    "RankingPage",
    "SeriesAnalyticsRow",
    "SponsorRankingRow",
    "UserStatisticsRow",
    "VariantRankingRow",
    "analytics_cache",
    "build_time_windows",
]
