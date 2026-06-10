from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminFileAction, AdminFileCallback, AdminSection
from admin.keyboards.navigation import navigation_row


def file_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📁 Add File", callback_data=AdminFileCallback(action=AdminFileAction.ADD).pack())],
            [InlineKeyboardButton(text="📋 File List", callback_data=AdminFileCallback(action=AdminFileAction.LIST).pack())],
            [InlineKeyboardButton(text="🔍 Search File", callback_data=AdminFileCallback(action=AdminFileAction.SEARCH).pack())],
            navigation_row(refresh=AdminSection.FILES),
        ]
    )


def file_list_keyboard(files: list[tuple[int, str]], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=AdminFileCallback(action=AdminFileAction.VIEW, file_id=file_id, page=page).pack())]
        for file_id, title in files
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=AdminFileCallback(action=AdminFileAction.PAGE, page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=AdminFileCallback(action=AdminFileAction.PAGE, page=page + 1).pack()))
    if nav:
        rows.append(nav)
    rows.append(navigation_row(back_to=AdminSection.FILES, refresh=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def file_detail_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Variant", callback_data=AdminFileCallback(action=AdminFileAction.ADD_VARIANT, file_id=file_id).pack())],
            [InlineKeyboardButton(text="✏️ Edit", callback_data=AdminFileCallback(action=AdminFileAction.VIEW, file_id=file_id).pack())],
            [InlineKeyboardButton(text="🗑 Delete", callback_data=AdminFileCallback(action=AdminFileAction.DELETE, file_id=file_id).pack())],
            [InlineKeyboardButton(text="🔗 Deep Links", callback_data=AdminFileCallback(action=AdminFileAction.LINKS, file_id=file_id).pack())],
            navigation_row(back_to=AdminSection.FILES, refresh=AdminSection.FILES),
        ]
    )


def premium_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Free", callback_data="file_premium:0"),
                InlineKeyboardButton(text="Premium", callback_data="file_premium:1"),
            ],
            navigation_row(back_to=AdminSection.FILES),
        ]
    )
