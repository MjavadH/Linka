from __future__ import annotations

from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import (
    AdminAnalyticsAction,
    AdminAnalyticsCallback,
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminSection,
)
from admin.keyboards import analytics_menu_keyboard, analytics_report_keyboard
from repositories.analytics import AnalyticsRepository
from services.analytics import (
    AnalyticsReportService,
    BroadcastStatisticsRow,
    DownloadStatisticsRow,
    OverviewStatisticsRow,
    PremiumStatisticsRow,
    UserStatisticsRow,
)

router = Router(name="admin_analytics")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.ANALYTICS))
async def open_analytics(callback: CallbackQuery) -> None:
    await show_analytics_menu(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.ANALYTICS)
        & (F.action.in_({AdminNavAction.BACK}))
    )
)
async def navigate_analytics(callback: CallbackQuery) -> None:
    await show_analytics_menu(callback)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.OVERVIEW))
async def show_overview(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await _service(session).overview()
    await _edit(callback, _overview_text(report), AdminAnalyticsAction.OVERVIEW)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.USERS))
async def show_users(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await _service(session).users()
    await _edit(callback, _users_text(report), AdminAnalyticsAction.USERS)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.PREMIUM))
async def show_premium(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await _service(session).premium()
    await _edit(callback, _premium_text(report), AdminAnalyticsAction.PREMIUM)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.DOWNLOADS))
async def show_downloads(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await _service(session).downloads()
    await _edit(callback, _downloads_text(report), AdminAnalyticsAction.DOWNLOADS)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.TOP_CONTENT))
async def show_top_content(callback: CallbackQuery, callback_data: AdminAnalyticsCallback, session: AsyncSession) -> None:
    service = _service(session)
    movies = await service.top_movies(callback_data.page)
    series = await service.top_series(callback_data.page)
    text = _top_content_text(movies.items, series.items, callback_data.page)
    await _edit(callback, text, AdminAnalyticsAction.TOP_CONTENT, callback_data.page, movies.has_next or series.has_next)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.TOP_VARIANTS))
async def show_top_variants(callback: CallbackQuery, callback_data: AdminAnalyticsCallback, session: AsyncSession) -> None:
    page = await _service(session).top_variants(callback_data.page)
    await _edit(callback, _top_variants_text(page.items, page.page), AdminAnalyticsAction.TOP_VARIANTS, page.page, page.has_next)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.SERIES))
async def show_series_analytics(callback: CallbackQuery, callback_data: AdminAnalyticsCallback, session: AsyncSession) -> None:
    page = await _service(session).series_analytics(callback_data.page)
    await _edit(callback, _series_analytics_text(page.items, page.page), AdminAnalyticsAction.SERIES, page.page, page.has_next)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.SPONSORS))
async def show_sponsor_analytics(callback: CallbackQuery, callback_data: AdminAnalyticsCallback, session: AsyncSession) -> None:
    page = await _service(session).sponsors(callback_data.page)
    await _edit(callback, _sponsors_text(page.items, page.page), AdminAnalyticsAction.SPONSORS, page.page, page.has_next)


@router.callback_query(AdminAnalyticsCallback.filter(F.action == AdminAnalyticsAction.BROADCASTS))
async def show_broadcast_analytics(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await _service(session).broadcasts()
    await _edit(callback, _broadcasts_text(report), AdminAnalyticsAction.BROADCASTS)


async def show_analytics_menu(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📊 <b>Analytics</b>\n\nChoose an admin-only report.",
            reply_markup=analytics_menu_keyboard(),
        )
    await callback.answer()


def _service(session: AsyncSession) -> AnalyticsReportService:
    return AnalyticsReportService(AnalyticsRepository(session))


async def _edit(callback: CallbackQuery, text: str, action: AdminAnalyticsAction, page: int = 1, has_next: bool = False) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=analytics_report_keyboard(action, page, has_next))
    await callback.answer()


def _overview_text(report: OverviewStatisticsRow) -> str:
    return (
        "📈 <b>Overview Report</b>\n\n"
        f"👥 Total Users: <b>{report.total_users}</b>\n"
        f"🟢 Active Users (30d): <b>{report.active_users}</b>\n"
        f"⭐ Premium Users: <b>{report.premium_users}</b>\n"
        f"🚫 Banned Users: <b>{report.banned_users}</b>\n\n"
        f"📥 Total Downloads: <b>{report.total_downloads}</b>\n"
        f"Today: <b>{report.downloads_today}</b> | Yesterday: <b>{report.downloads_yesterday}</b>\n"
        f"7 Days: <b>{report.downloads_last_7_days}</b> | 30 Days: <b>{report.downloads_last_30_days}</b>\n\n"
        f"🎬 Movies: <b>{report.total_movies}</b>\n"
        f"📺 Series: <b>{report.total_series}</b>\n"
        f"🎞 Episodes: <b>{report.total_episodes}</b>\n"
        f"🧩 Variants: <b>{report.total_variants}</b>"
    )


def _users_text(report: UserStatisticsRow) -> str:
    return (
        "👥 <b>User Analytics</b>\n\n"
        f"Total Users: <b>{report.total_users}</b>\n\n"
        f"New Today: <b>{report.new_today}</b>\n"
        f"New Yesterday: <b>{report.new_yesterday}</b>\n"
        f"New Last 7 Days: <b>{report.new_last_7_days}</b>\n"
        f"New Last 30 Days: <b>{report.new_last_30_days}</b>\n\n"
        f"Active Today: <b>{report.active_today}</b>\n"
        f"Active Last 7 Days: <b>{report.active_last_7_days}</b>\n"
        f"Active Last 30 Days: <b>{report.active_last_30_days}</b>\n\n"
        f"Users With Downloads: <b>{report.users_with_downloads}</b>\n"
        f"Users Without Downloads: <b>{report.users_without_downloads}</b>"
    )


def _premium_text(report: PremiumStatisticsRow) -> str:
    plans = "\n".join(
        f"• {escape(plan.plan_name)} — Active: <b>{plan.active_count}</b>, Expired: <b>{plan.expired_count}</b>"
        for plan in report.plan_statistics
    ) or "—"
    return (
        "⭐ <b>Premium Analytics</b>\n\n"
        f"Active Premium Users: <b>{report.active_premium_users}</b>\n"
        f"Expired Premium Users: <b>{report.expired_premium_users}</b>\n\n"
        f"Premium Users Today: <b>{report.premium_users_today}</b>\n"
        f"Premium Users Last 7 Days: <b>{report.premium_users_last_7_days}</b>\n"
        f"Premium Users Last 30 Days: <b>{report.premium_users_last_30_days}</b>\n\n"
        f"Most Popular Plan: <b>{escape(report.most_popular_plan)}</b>\n\n"
        f"<b>Per Plan Statistics</b>\n{plans}"
    )


def _downloads_text(report: DownloadStatisticsRow) -> str:
    return (
        "📥 <b>Download Analytics</b>\n\n"
        f"Total Downloads: <b>{report.total_downloads}</b>\n"
        f"Today: <b>{report.downloads_today}</b>\n"
        f"Yesterday: <b>{report.downloads_yesterday}</b>\n"
        f"Last 7 Days: <b>{report.downloads_last_7_days}</b>\n"
        f"Last 30 Days: <b>{report.downloads_last_30_days}</b>\n\n"
        f"Premium Downloads: <b>{report.premium_downloads}</b>\n"
        f"Free Downloads: <b>{report.free_downloads}</b>\n"
        f"Average Downloads Per User: <b>{report.average_downloads_per_user}</b>"
    )


def _top_content_text(movies: tuple[Any, ...], series: tuple[Any, ...], page: int) -> str:
    return (
        f"🏆 <b>Top Content</b> — Page {page}\n\n"
        "🎬 <b>Movies</b>\n"
        f"{_ranking_lines(movies)}\n\n"
        "📺 <b>Series</b>\n"
        f"{_ranking_lines(series)}"
    )


def _top_variants_text(items: tuple[Any, ...], page: int) -> str:
    lines = "\n\n".join(f"{index}. {escape(item.title)} - {escape(item.quality)}\nDownloads: <b>{item.downloads}</b>" for index, item in enumerate(items, start=1))
    return f"🎞 <b>Top Variants</b> — Page {page}\n\n{lines or '—'}"


def _series_analytics_text(items: tuple[Any, ...], page: int) -> str:
    lines = "\n\n".join(
        f"{index}. {escape(item.title)}\n"
        f"Total Downloads: <b>{item.total_downloads}</b>\n"
        f"Episode Count: <b>{item.episode_count}</b>\n"
        f"Most Downloaded: <b>{escape(item.most_downloaded_episode)}</b>\n"
        f"Least Downloaded: <b>{escape(item.least_downloaded_episode)}</b>\n"
        f"Average/Episode: <b>{item.average_downloads_per_episode}</b>"
        for index, item in enumerate(items, start=1)
    )
    return f"📺 <b>Series Analytics</b> — Page {page}\n\n{lines or '—'}"


def _sponsors_text(items: tuple[Any, ...], page: int) -> str:
    lines = "\n\n".join(
        f"{index}. {escape(item.name)}\n"
        f"Verified Users: <b>{item.verified_users}</b>\n"
        f"Current Members: <b>{item.current_member_count or 0}</b>\n"
        f"Expiration Type: <b>{escape(item.expiration_type)}</b>\n"
        f"Status: <b>{escape(item.status)}</b>"
        for index, item in enumerate(items, start=1)
    )
    return f"🤝 <b>Sponsor Analytics</b> — Page {page}\n\n{lines or '—'}"


def _broadcasts_text(report: BroadcastStatisticsRow) -> str:
    last = report.last_broadcast_date.strftime("%Y-%m-%d %H:%M UTC") if report.last_broadcast_date else "—"
    most = f"#{report.most_successful_broadcast_id} ({report.most_successful_broadcast_delivered} delivered)" if report.most_successful_broadcast_id else "—"
    return (
        "📢 <b>Broadcast Reports</b>\n\n"
        f"Total Broadcasts: <b>{report.total_broadcasts}</b>\n"
        f"Successful Broadcasts: <b>{report.successful_broadcasts}</b>\n"
        f"Cancelled Broadcasts: <b>{report.cancelled_broadcasts}</b>\n"
        f"Last Broadcast Date: <b>{escape(last)}</b>\n"
        f"Most Successful Broadcast: <b>{escape(most)}</b>"
    )


def _ranking_lines(items: tuple[Any, ...]) -> str:
    return "\n\n".join(f"{index}. {escape(item.title)}\nDownloads: <b>{item.downloads}</b>" for index, item in enumerate(items, start=1)) or "—"
