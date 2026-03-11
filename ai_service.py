"""
AI Service — Anthropic Claude + Vosk Speech-to-Text
"""
import os
import json
import wave
import subprocess
import anthropic
from config import ANTHROPIC_API_KEY

# ═══════════════════════════════════════════════════════════════
# ANTHROPIC CLAUDE (анализ эмоций)
# ═══════════════════════════════════════════════════════════════

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
        2: "что было вне его контроля в этой ситуации",
        3: "что он почувствовал в теле или в мыслях",
        4: "что было в твоей зоне влияния",
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
        2: "Что в этой ситуации было вне твоего контроля?",
        3: "Что ты почувствовал в теле или в мыслях?",
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
        return json.loads(message.content[0].text.strip())
    except Exception:
        return {"mood": "neutral", "insight": ""}


# ═══════════════════════════════════════════════════════════════
# VOSK SPEECH-TO-TEXT (оффлайн транскрибация)
# ═══════════════════════════════════════════════════════════════

from vosk import Model, KaldiRecognizer

# Путь к модели Vosk (в папке проекта)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOSK_MODEL_PATH = os.path.join(BASE_DIR, "vosk-model-small-ru-0.22")

# Кэш модели
_vosk_model = None


def get_vosk_model():
    """Загрузить модель Vosk (кэшируется)."""
    global _vosk_model
    if _vosk_model is None:
        if not os.path.exists(VOSK_MODEL_PATH):
            raise FileNotFoundError(
                f"Модель Vosk не найдена: {VOSK_MODEL_PATH}\n"
                f"Скачай: wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip\n"
                f"Распакуй в: {BASE_DIR}"
            )
        from vosk import Model
        _vosk_model = Model(VOSK_MODEL_PATH)
    return _vosk_model


async def transcribe_voice_vosk(file_path: str) -> dict:
    """
    Транскрибация через Vosk (оффлайн).
    file_path: путь к .ogg или .wav файлу
    
    Возвращает:
    {
        "text": "распознанный текст",
        "duration": 15.5,  # длительность в секундах
        "language": "ru",
        "service": "vosk"
    }
    """
    try:
        # Конвертировать Ogg → WAV (если нужно)
        wav_path = convert_ogg_to_wav(file_path)
        
        # Открыть WAV файл
        wf = wave.open(wav_path, "rb")
        
        # Проверка формата
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError("Неверный формат WAV. Нужно: mono, 16-bit")
        
        # Создать распознаватель
        model = get_vosk_model()
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)  # Возвращать тайминги слов
        
        # Распознавание
        text_parts = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    text_parts.append(result["text"])
        
        # Финальный результат
        final_result = json.loads(rec.FinalResult())
        if final_result.get("text"):
            text_parts.append(final_result["text"])
        
        full_text = " ".join(text_parts).strip()
        
        # Длительность
        duration = wf.getnframes() / wf.getframerate()
        wf.close()
        
        # Удалить временный файл
        if wav_path != file_path:
            os.remove(wav_path)
        
        return {
            "text": full_text,
            "duration": duration,
            "language": "ru",
            "service": "vosk"
        }
        
    except Exception as e:
        return {"text": "", "error": str(e)}


def convert_ogg_to_wav(ogg_path: str) -> str:
    """
    Конвертировать Ogg (из Telegram) в WAV для Vosk.
    Vosk требует: WAV, 16kHz, mono, 16-bit PCM
    """
    wav_path = ogg_path.replace(".ogg", ".wav")
    
    # Использовать ffmpeg для конвертации
    subprocess.run([
        "ffmpeg",
        "-i", ogg_path,
        "-ar", "16000",      # 16 kHz
        "-ac", "1",          # mono
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-y",                # перезаписать если есть
        wav_path
    ], check=True, capture_output=True)
    
    return wav_path
