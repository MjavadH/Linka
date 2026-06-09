from aiogram.fsm.state import State, StatesGroup


class AdminSponsorStates(StatesGroup):
    waiting_for_chat_id = State()
    waiting_for_invite_url = State()
    waiting_for_campaign_name = State()
