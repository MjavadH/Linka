from aiogram.fsm.state import State, StatesGroup


class AdminSponsorStates(StatesGroup):
    waiting_for_forwarded_message = State()
    waiting_for_invite_url = State()
    waiting_for_expiration_date = State()
    waiting_for_expiration_time = State()
    waiting_for_join_count = State()
    waiting_for_edit_invite_url = State()
    waiting_for_edit_expiration_date = State()
    waiting_for_edit_expiration_time = State()
    waiting_for_edit_join_count = State()
    waiting_for_campaign_name = State()
