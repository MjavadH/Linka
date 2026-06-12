import asyncio
from datetime import UTC, datetime
from typing import Any

from repositories.analytics import (
    BroadcastStatisticsRow,
    ContentRankingRow,
    DownloadStatisticsRow,
    OverviewStatisticsRow,
    PremiumPlanStatisticsRow,
    PremiumStatisticsRow,
    RankingPage,
    SponsorRankingRow,
    UserStatisticsRow,
    VariantRankingRow,
)
from services.analytics import AnalyticsReportService, ReportCache


class FakeAnalyticsRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def overview(self, **kwargs: Any) -> OverviewStatisticsRow:
        self.calls.append(("overview", kwargs))
        return OverviewStatisticsRow(100, 80, 12, 2, 500, 8, 7, 70, 300, 20, 4, 40, 60)

    async def users(self, **kwargs: Any) -> UserStatisticsRow:
        self.calls.append(("users", kwargs))
        return UserStatisticsRow(100, 3, 4, 15, 35, 10, 45, 80, 70, 30)

    async def premium(self, **kwargs: Any) -> PremiumStatisticsRow:
        self.calls.append(("premium", kwargs))
        return PremiumStatisticsRow(
            12,
            8,
            2,
            6,
            10,
            "Diamond",
            (PremiumPlanStatisticsRow("Diamond", 7, 3), PremiumPlanStatisticsRow("Gold", 5, 5)),
        )

    async def downloads(self, **kwargs: Any) -> DownloadStatisticsRow:
        self.calls.append(("downloads", kwargs))
        return DownloadStatisticsRow(500, 8, 7, 70, 300, 120, 380, 5.0)

    async def top_movies(self, page: int, page_size: int) -> RankingPage:
        self.calls.append(("top_movies", {"page": page, "page_size": page_size}))
        return RankingPage((ContentRankingRow(1, "Movie A", 5200), ContentRankingRow(2, "Movie B", 4800)), page, page_size, True)

    async def top_series(self, page: int, page_size: int) -> RankingPage:
        self.calls.append(("top_series", {"page": page, "page_size": page_size}))
        return RankingPage((ContentRankingRow(10, "Series X", 8200),), page, page_size, False)

    async def top_variants(self, page: int, page_size: int) -> RankingPage:
        self.calls.append(("top_variants", {"page": page, "page_size": page_size}))
        return RankingPage((VariantRankingRow(100, "Movie A", "720p", 3100), VariantRankingRow(101, "Movie A", "1080p", 2200)), page, page_size, True)

    async def series_analytics(self, page: int, page_size: int) -> RankingPage:
        self.calls.append(("series_analytics", {"page": page, "page_size": page_size}))
        return RankingPage((), page, page_size, False)

    async def sponsors(self, page: int, page_size: int) -> RankingPage:
        self.calls.append(("sponsors", {"page": page, "page_size": page_size}))
        return RankingPage((SponsorRankingRow(1, "Anime Channel", 1450, 21000, "members", "Active"),), page, page_size, False)

    async def broadcasts(self) -> BroadcastStatisticsRow:
        self.calls.append(("broadcasts", {}))
        return BroadcastStatisticsRow(5, 3, 1, datetime(2026, 6, 12, tzinfo=UTC), 4, 900)


def test_overview_statistics_are_returned_and_cached() -> None:
    async def scenario() -> None:
        repo = FakeAnalyticsRepository()
        service = AnalyticsReportService(repo, ReportCache())
        first = await service.overview()
        second = await service.overview()
        assert first.total_users == 100
        assert first.downloads_last_30_days == 300
        assert second is first
        assert [call[0] for call in repo.calls] == ["overview"]

    asyncio.run(scenario())


def test_premium_statistics_include_plan_breakdown() -> None:
    async def scenario() -> None:
        stats = await AnalyticsReportService(FakeAnalyticsRepository(), ReportCache()).premium()
        assert stats.active_premium_users == 12
        assert stats.expired_premium_users == 8
        assert stats.most_popular_plan == "Diamond"
        assert stats.plan_statistics[0].active_count == 7
        assert stats.plan_statistics[1].expired_count == 5

    asyncio.run(scenario())


def test_download_statistics_include_free_premium_and_average() -> None:
    async def scenario() -> None:
        stats = await AnalyticsReportService(FakeAnalyticsRepository(), ReportCache()).downloads()
        assert stats.total_downloads == 500
        assert stats.premium_downloads == 120
        assert stats.free_downloads == 380
        assert stats.average_downloads_per_user == 5.0

    asyncio.run(scenario())


def test_top_content_rankings_cover_movies_and_series() -> None:
    async def scenario() -> None:
        service = AnalyticsReportService(FakeAnalyticsRepository(), ReportCache())
        movies = await service.top_movies(page=2, page_size=2)
        series = await service.top_series(page=2, page_size=2)
        assert [item.title for item in movies.items] == ["Movie A", "Movie B"]
        assert movies.items[0].downloads > movies.items[1].downloads
        assert [item.title for item in series.items] == ["Series X"]

    asyncio.run(scenario())


def test_top_variant_rankings_are_paginated() -> None:
    async def scenario() -> None:
        page = await AnalyticsReportService(FakeAnalyticsRepository(), ReportCache()).top_variants(page=3, page_size=2)
        assert page.page == 3
        assert page.has_next is True
        assert page.items[0].quality == "720p"
        assert page.items[0].downloads > page.items[1].downloads

    asyncio.run(scenario())


def test_sponsor_rankings_use_verified_join_counts() -> None:
    async def scenario() -> None:
        page = await AnalyticsReportService(FakeAnalyticsRepository(), ReportCache()).sponsors(page=1, page_size=5)
        sponsor = page.items[0]
        assert sponsor.name == "Anime Channel"
        assert sponsor.verified_users == 1450
        assert sponsor.current_member_count == 21000
        assert sponsor.status == "Active"

    asyncio.run(scenario())


def test_broadcast_reports_include_success_and_last_broadcast() -> None:
    async def scenario() -> None:
        stats = await AnalyticsReportService(FakeAnalyticsRepository(), ReportCache()).broadcasts()
        assert stats.total_broadcasts == 5
        assert stats.successful_broadcasts == 3
        assert stats.cancelled_broadcasts == 1
        assert stats.last_broadcast_date == datetime(2026, 6, 12, tzinfo=UTC)
        assert stats.most_successful_broadcast_id == 4

    asyncio.run(scenario())


def test_pagination_parameters_are_passed_to_repository() -> None:
    async def scenario() -> None:
        repo = FakeAnalyticsRepository()
        await AnalyticsReportService(repo, ReportCache()).top_movies(page=4, page_size=9)
        assert repo.calls == [("top_movies", {"page": 4, "page_size": 9})]

    asyncio.run(scenario())
