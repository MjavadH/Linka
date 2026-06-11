from aiogram.fsm.state import State, StatesGroup


class AdminPremiumStates(StatesGroup):
    waiting_for_plan_name = State()
    waiting_for_plan_duration = State()
    waiting_for_plan_price = State()
    waiting_for_plan_description = State()
    waiting_for_edit_value = State()
    waiting_for_user = State()
    waiting_for_setting_value = State()
