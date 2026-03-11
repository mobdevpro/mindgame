from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_subscription = State()


class TriggerStates(StatesGroup):
    waiting_trigger_text = State()
    waiting_emotion = State()
    waiting_intensity = State()
    waiting_zone = State()
    waiting_insight = State()
    waiting_next_action = State()
    # Reflection states (3 steps)
    reflect_step_1 = State()
    reflect_step_2 = State()
    reflect_step_3 = State()


class DiaryStates(StatesGroup):
    waiting_entry = State()
    waiting_mood = State()
    waiting_energy = State()
    waiting_insight = State()


class CheckinStates(StatesGroup):
    waiting_feeling = State()
    waiting_energy = State()
    waiting_tension = State()


class TaskStates(StatesGroup):
    waiting_text = State()
    waiting_difficulty = State()


class StopStates(StatesGroup):
    step_feeling = State()
    step_intensity = State()
    step_pause = State()
