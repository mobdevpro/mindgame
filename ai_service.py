import anthropic
from config import ANTHROPIC_API_KEY

_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


EMOTION_LABELS = {
    "anger": "😤 Злость",
    "sadness": "😔 Грусть",
    "fear": "😨 Страх",
    "shame": "😳 Стыд",
    "anxiety": "😟 Тревога",
    "resentment": "😞 Обида",
    "irritation": "😤 Раздражение",
    "numbness": "😶 Онемение",
    "other": "💭 Другое",
}

CATEGORY_LABELS = {
    "relationships": "👥 Отношения",
    "work": "💼 Работа",
    "self_image": "🪞 Образ себя",
    "boundaries": "🚧 Границы",
    "recognition": "🏅 Признание",
    "control": "🎛 Контроль",
    "abandonment": "💔 Покинутость",
    "other": "💭 Другое",
}


async def analyze_trigger(text: str) -> dict:
    """Analyze trigger text: detect emotion and category using Claude."""
    if not ANTHROPIC_API_KEY:
        return {"emotion": "other", "category": "other", "ai_response": ""}

    try:
        client = get_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Проанализируй этот триггер (эмоциональную реакцию):

"{text}"

Ответь ТОЛЬКО в формате JSON (без ```json```, только чистый JSON):
{{
  "emotion": "<одно из: anger, sadness, fear, shame, anxiety, resentment, irritation, numbness, other>",
  "category": "<одно из: relationships, work, self_image, boundaries, recognition, control, abandonment, other>",
  "brief_response": "<короткий (1-2 предложения) эмпатичный ответ-наблюдение без обвинений>"
}}"""
            }]
        )
        import json
        result = json.loads(message.content[0].text.strip())
        return result
    except Exception as e:
        return {"emotion": "other", "category": "other", "brief_response": "Спасибо, что зафиксировал это."}


async def generate_reflection_prompt(trigger_text: str, emotion: str, step: int) -> str:
    """Generate a contextual reflection question for the given step."""
    if not ANTHROPIC_API_KEY:
        return _default_reflection(step)

    steps = {
        1: "что именно задело человека в этой ситуации",
        2: "что он почувствовал в теле или в голове",
        3: "что было вне его контроля в этой ситуации",
        4: "что было в его зоне влияния",
        5: "какой следующий зрелый шаг он может сделать",
    }
    focus = steps.get(step, "рефлексию")

    try:
        client = get_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"""Человек зафиксировал триггер: "{trigger_text}"
Эмоция: {emotion}

Сформулируй один короткий вопрос для рефлексии на тему: {focus}.
Без обвинений, экологично, с позиции наблюдателя.
Только вопрос, без лишнего текста."""
            }]
        )
        return message.content[0].text.strip()
    except Exception:
        return _default_reflection(step)


def _default_reflection(step: int) -> str:
    defaults = {
        1: "Что именно тебя задело в этой ситуации?",
        2: "Что ты почувствовал в теле или в мыслях?",
        3: "Что в этой ситуации было вне твоего контроля?",
        4: "Что было в твоей зоне влияния?",
        5: "Какой зрелый следующий шаг ты можешь сделать?",
    }
    return defaults.get(step, "Что ты заметил в себе?")


async def classify_diary_mood(text: str) -> dict:
    """Extract mood and insight from diary entry."""
    if not ANTHROPIC_API_KEY:
        return {"mood": "neutral", "insight": ""}

    try:
        client = get_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Запись дневника осознанности:

"{text}"

Ответь ТОЛЬКО в формате JSON:
{{
  "mood": "<одно из: good, neutral, bad, tense, tired, energetic>",
  "insight": "<краткий инсайт 1 предложение, что человек заметил о себе>"
}}"""
            }]
        )
        import json
        return json.loads(message.content[0].text.strip())
    except Exception:
        return {"mood": "neutral", "insight": ""}
