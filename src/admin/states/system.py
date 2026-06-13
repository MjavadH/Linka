from aiogram.fsm.state import State, StatesGroup


class AdminSystemStates(StatesGroup):
    waiting_for_search_date = State()
    waiting_for_search_log_id = State()
