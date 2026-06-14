from itertools import batched

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminFileAction, AdminFileCallback, AdminSection
from admin.keyboards.navigation import navigation_row
from models.file import Episode, FileVariant


def file_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Content", callback_data=AdminFileCallback(action=AdminFileAction.ADD).pack())],
            [
                InlineKeyboardButton(text="🎬 Movies", callback_data=AdminFileCallback(action=AdminFileAction.LIST_MOVIES).pack()),
                InlineKeyboardButton(text="📺 Series", callback_data=AdminFileCallback(action=AdminFileAction.LIST_SERIES).pack()),
            ],
            [InlineKeyboardButton(text="🔍 Search", callback_data=AdminFileCallback(action=AdminFileAction.SEARCH).pack())],
            navigation_row(),
        ]
    )


def content_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Movie", callback_data=AdminFileCallback(action=AdminFileAction.ADD_MOVIE).pack()),
                InlineKeyboardButton(text="📺 Series", callback_data=AdminFileCallback(action=AdminFileAction.ADD_SERIES).pack()),
            ],
            navigation_row(back_to=AdminSection.FILES),
        ]
    )


def file_list_keyboard(files: list[tuple[int, str]], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=title, callback_data=AdminFileCallback(action=AdminFileAction.VIEW, file_id=file_id, page=page).pack())
            for file_id, title in chunk
        ]
        for chunk in batched(files, 2)
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminFileCallback(action=AdminFileAction.PAGE, page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminFileCallback(action=AdminFileAction.PAGE, page=page + 1).pack()))
    if nav:
        rows.append(nav)
    rows.append(navigation_row(back_to=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_list_keyboard(series: list[tuple[int, str]], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=title, callback_data=AdminFileCallback(action=AdminFileAction.VIEW_SERIES, series_id=series_id, page=page).pack())
            for series_id, title in chunk
        ]
        for chunk in batched(series, 2)
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminFileCallback(action=AdminFileAction.SERIES_PAGE, page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminFileCallback(action=AdminFileAction.SERIES_PAGE, page=page + 1).pack()))
    if nav:
        rows.append(nav)
    rows.append(navigation_row(back_to=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_detail_keyboard(series_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Episode", callback_data=AdminFileCallback(action=AdminFileAction.ADD_EPISODE, series_id=series_id).pack())],
        [InlineKeyboardButton(text="📋 Episodes List", callback_data=AdminFileCallback(action=AdminFileAction.EPISODES, series_id=series_id).pack())],
        [InlineKeyboardButton(text="✏️ Edit Series", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_SERIES, series_id=series_id).pack())],
        [InlineKeyboardButton(text="🗑 Delete Series", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_SERIES, series_id=series_id).pack())],
        navigation_row(back_to=AdminSection.FILES),
    ])


def episodes_list_keyboard(series_id: int, episodes: list[Episode], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=f"Episode {episode.number}", callback_data=AdminFileCallback(action=AdminFileAction.VIEW_EPISODE, series_id=series_id, episode_id=episode.id, page=page).pack())
            for episode in chunk
        ]
        for chunk in batched(episodes, 2)
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminFileCallback(action=AdminFileAction.EPISODES_PAGE, series_id=series_id, page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminFileCallback(action=AdminFileAction.EPISODES_PAGE, series_id=series_id, page=page + 1).pack()))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Series Details", callback_data=AdminFileCallback(action=AdminFileAction.VIEW_SERIES, series_id=series_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_detail_keyboard(series_id: int, episode_id: int, file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Variant", callback_data=AdminFileCallback(action=AdminFileAction.ADD_VARIANT, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="✏️ Edit Episode", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_EPISODE, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="🗑 Delete Episode", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_EPISODE, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="📋 Variant List", callback_data=AdminFileCallback(action=AdminFileAction.EPISODE_VARIANTS, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="❌ Delete Variant", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_VARIANT, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="🔗 Deep Links", callback_data=AdminFileCallback(action=AdminFileAction.LINKS, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="⬅️ Series Details", callback_data=AdminFileCallback(action=AdminFileAction.VIEW_SERIES, series_id=series_id).pack())],
    ])


def file_detail_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Variant", callback_data=AdminFileCallback(action=AdminFileAction.ADD_VARIANT, file_id=file_id).pack())],
        [InlineKeyboardButton(text="✏️ Edit", callback_data=AdminFileCallback(action=AdminFileAction.EDIT, file_id=file_id).pack())],
        [InlineKeyboardButton(text="🗑 Delete File", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_FILE, file_id=file_id).pack())],
        [InlineKeyboardButton(text="❌ Delete Variant", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_VARIANT, file_id=file_id).pack())],
        [InlineKeyboardButton(text="🔗 Deep Links", callback_data=AdminFileCallback(action=AdminFileAction.LINKS, file_id=file_id).pack())],
        navigation_row(back_to=AdminSection.FILES),
    ])


def file_edit_keyboard(file_id: int, variants: list[FileVariant]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✏️ Title", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_TITLE, file_id=file_id).pack())],
        [InlineKeyboardButton(text="📝 Description/Caption", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_CAPTION, file_id=file_id).pack())],
    ]
    rows.extend([[InlineKeyboardButton(text=f"🎞 {variant.quality}", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT, file_id=file_id, variant_id=variant.id).pack())] for variant in variants if variant.is_active])
    rows.append(navigation_row(back_to=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def variant_edit_keyboard(file_id: int, variant_id: int, series_id: int = 0, episode_id: int = 0) -> InlineKeyboardMarkup:
    back_action = AdminFileAction.VIEW_EPISODE if episode_id else AdminFileAction.VIEW
    back_text = "⬅️ Episode Details" if episode_id else "⬅️ File Details"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷 Quality Label", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_QUALITY, file_id=file_id, variant_id=variant_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="⭐ Premium Status", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_PREMIUM, file_id=file_id, variant_id=variant_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="📝 Variant Caption", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_CAPTION, file_id=file_id, variant_id=variant_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text="🗄 Storage Metadata", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_STORAGE, file_id=file_id, variant_id=variant_id, series_id=series_id, episode_id=episode_id).pack())],
        [InlineKeyboardButton(text=back_text, callback_data=AdminFileCallback(action=back_action, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())],
    ])


def variant_selection_keyboard(file_id: int, variants: list[FileVariant], action: AdminFileAction, series_id: int = 0, episode_id: int = 0) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=variant.quality, callback_data=AdminFileCallback(action=action, file_id=file_id, variant_id=variant.id, series_id=series_id, episode_id=episode_id).pack())] for variant in variants if variant.is_active]
    back_action = AdminFileAction.VIEW_EPISODE if episode_id else AdminFileAction.VIEW
    rows.append([InlineKeyboardButton(text="⬅️ Details", callback_data=AdminFileCallback(action=back_action, file_id=file_id, series_id=series_id, episode_id=episode_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_choice_keyboard(file_id: int = 0, variant_id: int = 0, series_id: int = 0, episode_id: int = 0) -> InlineKeyboardMarkup:
    suffix = f":{file_id}:{variant_id}:{series_id}:{episode_id}" if file_id or variant_id or series_id or episode_id else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆓 Free", callback_data=f"file_premium:0{suffix}"),
            InlineKeyboardButton(text="💎 Premium", callback_data=f"file_premium:1{suffix}"),
        ],
        navigation_row(back_to=AdminSection.FILES),
    ])
