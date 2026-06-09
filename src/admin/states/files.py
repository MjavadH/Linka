from aiogram.fsm.state import State, StatesGroup


class AdminFileStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_title = State()
    waiting_for_access_level = State()
