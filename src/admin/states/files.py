from aiogram.fsm.state import State, StatesGroup


class AdminFileStates(StatesGroup):
    waiting_for_upload = State()
    waiting_for_title = State()
    waiting_for_quality = State()
    waiting_for_premium = State()
    waiting_for_search = State()
    waiting_for_variant_upload = State()
    waiting_for_variant_quality = State()
    waiting_for_variant_premium = State()
