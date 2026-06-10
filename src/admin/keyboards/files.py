from itertools import batched

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminFileAction, AdminFileCallback, AdminSection
from admin.keyboards.navigation import navigation_row
from models.file import FileVariant


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
        [
            InlineKeyboardButton(
                text=title,
                callback_data=AdminFileCallback(
                    action=AdminFileAction.VIEW,
                    file_id=file_id,
                    page=page,
                ).pack(),
            )
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
    rows.append(navigation_row(back_to=AdminSection.FILES, refresh=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def file_detail_keyboard(file_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Variant", callback_data=AdminFileCallback(action=AdminFileAction.ADD_VARIANT, file_id=file_id).pack())],
            [InlineKeyboardButton(text="✏️ Edit", callback_data=AdminFileCallback(action=AdminFileAction.EDIT, file_id=file_id).pack())],
            [InlineKeyboardButton(text="🗑 Delete File", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_FILE, file_id=file_id).pack())],
            [InlineKeyboardButton(text="❌ Delete Variant", callback_data=AdminFileCallback(action=AdminFileAction.DELETE_VARIANT, file_id=file_id).pack())],
            [InlineKeyboardButton(text="🔗 Deep Links", callback_data=AdminFileCallback(action=AdminFileAction.LINKS, file_id=file_id).pack())],
            navigation_row(back_to=AdminSection.FILES, refresh=AdminSection.FILES),
        ]
    )


def file_edit_keyboard(file_id: int, variants: list[FileVariant]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✏️ Title", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_TITLE, file_id=file_id).pack())],
        [InlineKeyboardButton(text="📝 Description/Caption", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_CAPTION, file_id=file_id).pack())],
    ]
    rows.extend(
        [
            InlineKeyboardButton(
                text=f"🎞 {variant.quality}",
                callback_data=AdminFileCallback(
                    action=AdminFileAction.EDIT_VARIANT,
                    file_id=file_id,
                    variant_id=variant.id,
                ).pack(),
            )
        ]
        for variant in variants
        if variant.is_active
    )
    rows.append(navigation_row(back_to=AdminSection.FILES, refresh=AdminSection.FILES))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def variant_edit_keyboard(file_id: int, variant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏷 Quality Label", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_QUALITY, file_id=file_id, variant_id=variant_id).pack())],
            [InlineKeyboardButton(text="⭐ Premium Status", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_PREMIUM, file_id=file_id, variant_id=variant_id).pack())],
            [InlineKeyboardButton(text="📝 Variant Caption", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_CAPTION, file_id=file_id, variant_id=variant_id).pack())],
            [InlineKeyboardButton(text="🗄 Storage Metadata", callback_data=AdminFileCallback(action=AdminFileAction.EDIT_VARIANT_STORAGE, file_id=file_id, variant_id=variant_id).pack())],
            [InlineKeyboardButton(text="⬅️ File Details", callback_data=AdminFileCallback(action=AdminFileAction.VIEW, file_id=file_id).pack())],
        ]
    )


def variant_selection_keyboard(file_id: int, variants: list[FileVariant], action: AdminFileAction) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=variant.quality,
                callback_data=AdminFileCallback(action=action, file_id=file_id, variant_id=variant.id).pack(),
            )
        ]
        for variant in variants
        if variant.is_active
    ]
    rows.append([InlineKeyboardButton(text="⬅️ File Details", callback_data=AdminFileCallback(action=AdminFileAction.VIEW, file_id=file_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_choice_keyboard(file_id: int = 0, variant_id: int = 0) -> InlineKeyboardMarkup:
    suffix = f":{file_id}:{variant_id}" if file_id and variant_id else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Free", callback_data=f"file_premium:0{suffix}"),
                InlineKeyboardButton(text="Premium", callback_data=f"file_premium:1{suffix}"),
            ],
            navigation_row(back_to=AdminSection.FILES),
        ]
    )
