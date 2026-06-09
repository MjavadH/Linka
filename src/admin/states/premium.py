from aiogram.fsm.state import State, StatesGroup


class AdminPremiumStates(StatesGroup):
    waiting_for_user = State()
    waiting_for_duration = State()
    waiting_for_note = State()
