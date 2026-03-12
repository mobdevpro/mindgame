"""
AI Service — Google Gemini (free) + Hugging Face + Groq + Anthropic Claude + Vosk
"""
import os
import json
import wave
import subprocess
import anthropic
from config import ANTHROPIC_API_KEY

# Google Gemini API (бесплатно, 1500 запросов/день)
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
    else:
        gemini_model = None
except ImportError:
    gemini_model = None

# Hugging Face Inference API (бесплатно, 30K токенов/мес)
try:
    from huggingface_hub import InferenceClient
    HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
    hf_client = InferenceClient(token=HF_API_KEY) if HF_API_KEY else None
except ImportError:
    hf_client = None

# Groq Cloud (бесплатно, без лимита)
try:
    from groq import Groq
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except ImportError:
    groq_client = None

# ═══════════════════════════════════════════════════════════════
# AI ANALYSIS (анализ эмоций)
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
    "health": "💪 Здоровье",
    "money": "💰 Финансы",
    "other": "💭 Другое",
}


async def analyze_trigger(text: str) -> dict:
    """Analyze trigger text: detect emotion and category using AI."""
    
    # 1. Google Gemini (бесплатно, 1500 запросов/день, лучшее качество)
    if gemini_model:
        try:
            return await _analyze_with_gemini(text)
        except Exception as e:
            import logging
            logging.warning(f"Gemini failed: {e}")
    
    # 2. Hugging Face (бесплатно, 30K токенов/мес)
    if hf_client:
        try:
            return await _analyze_with_huggingface(text)
        except Exception as e:
            import logging
            logging.warning(f"Hugging Face failed: {e}")
    
    # 3. Groq (бесплатно, без лимита, очень быстро)
    if groq_client:
        try:
            return await _analyze_with_groq(text)
        except Exception as e:
            import logging
            logging.warning(f"Groq failed: {e}")
    
    # 4. Claude (платно, лучшее качество)
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here":
        try:
            return await _analyze_with_claude(text)
        except Exception as e:
            import logging
            logging.warning(f"Claude failed: {e}")
    
    # 5. Дефолт если ничего не работает
    return {"emotion": "other", "category": "other", "brief_response": "Спасибо, что зафиксировал это."}


async def _analyze_with_gemini(text: str) -> dict:
    """Анализ через Google Gemini (бесплатно, 1500 запросов/день)."""
    prompt = f"""Analyze this emotional trigger:

"{text}"

Choose ONE emotion: anger, irritation, sadness, fear, anxiety, shame, resentment, numbness, other
Choose ONE category: relationships, work, self_image, boundaries, recognition, control, abandonment, health, money, other

Reply ONLY with valid JSON (no markdown, no code blocks):
{{"emotion": "code", "category": "code", "brief_response": "1-2 sentences in Russian, empathetic observation"}}"""

    response = gemini_model.generate_content(prompt)
    result = json.loads(response.text.strip())
    return result


async def _analyze_with_huggingface(text: str) -> dict:
    """Анализ через Hugging Face Inference API (бесплатно)."""
    prompt = f"""Analyze this trigger: "{text}"

Choose ONE emotion: anger, irritation, sadness, fear, anxiety, shame, resentment, numbness, other
Choose ONE category: relationships, work, self_image, boundaries, recognition, control, abandonment, health, money, other

Reply ONLY with valid JSON:
{{"emotion": "code", "category": "code", "brief_response": "1-2 sentences in Russian"}}"""

    # Пробуем несколько моделей
    models_to_try = [
        'Qwen/Qwen2.5-7B-Instruct',
        'meta-llama/Llama-3.2-3B-Instruct',
        'mistralai/Mistral-7B-Instruct-v0.3',
    ]
    
    for model in models_to_try:
        try:
            response = hf_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            content = response.choices[0].message.content.strip()
            # Извлекаем JSON из ответа
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except Exception:
            continue
    
    # Если все модели не сработали
    raise Exception("All Hugging Face models failed")


async def _analyze_with_groq(text: str) -> dict:
    """Анализ через Groq Cloud (бесплатно)."""
    completion = groq_client.chat.completions.create(
        model="llama-3.2-3b-instant",
        messages=[{
            "role": "user",
            "content": f"""Проанализируй этот триггер:

"{text}"

Выбери ОДНУ эмоцию: anger, irritation, sadness, fear, anxiety, shame, resentment, numbness, other
Выбери ОДНУ категорию: relationships, work, self_image, boundaries, recognition, control, abandonment, health, money, other

Ответь ТОЛЬКО JSON:
{{
  "emotion": "<код>",
  "category": "<код>",
  "brief_response": "<1-2 предложения>"
}}"""
        }],
        temperature=0.3,
        max_tokens=200
    )
    result = json.loads(completion.choices[0].message.content.strip())
    return result


async def _analyze_with_claude(text: str) -> dict:
    """Анализ через Anthropic Claude."""
    client = get_client()
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Проанализируй этот триггер (эмоциональную реакцию):

"{text}"

Выбери ОДНУ основную эмоцию из списка:
- anger (Злость, гнев, ярость)
- irritation (Раздражение, недовольство)
- sadness (Грусть, печаль, тоска)
- fear (Страх, испуг)
- anxiety (Тревога, беспокойство, нервное напряжение)
- shame (Стыд, вина, неловкость)
- resentment (Обида, разочарование в человеке)
- numbness (Онемение, пустота, отсутствие чувств)
- other (Другое, если ничего не подходит)

Выбери ОДНУ категорию причины из списка:
- relationships (Отношения с партнёром, семьёй, друзьями)
- work (Работа, карьера, дедлайны, задачи)
- self_image (Образ себя, самооценка, сравнение с другими)
- boundaries (Личные границы, когда их нарушают)
- recognition (Признание, когда не ценят, игнорируют)
- control (Контроль, когда всё идёт не по плану)
- abandonment (Покинутость, одиночество, отвержение)
- health (Здоровье, усталость, физическое состояние)
- money (Финансы, деньги, покупки)
- other (Другое, если ничего не подходит)

Ответь ТОЛЬКО в формате JSON (без ```json```, только чистый JSON):
{{
  "emotion": "<код эмоции>",
  "category": "<код категории>",
  "brief_response": "<короткий (1-2 предложения) эмпатичный ответ-наблюдение без обвинений>"
}}"""
        }]
    )
    result = json.loads(message.content[0].text.strip())
    return result


async def generate_reflection_prompt(trigger_text: str, emotion: str, step: int) -> str:
    """Generate a contextual reflection question for the given step."""
    if not ANTHROPIC_API_KEY:
        return _default_reflection(step)

    steps = {
        1: "что именно задело человека в этой ситуации",
        2: "что он почувствовал в теле или в мыслях",
        3: "что было вне его контроля в этой ситуации",
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
