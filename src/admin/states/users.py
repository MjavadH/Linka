from aiogram.fsm.state import State, StatesGroup


class AdminUserStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_custom_premium_days = State()
    waiting_for_temporary_ban_days = State()
    waiting_for_message = State()
