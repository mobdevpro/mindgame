"""
Telegram Mini App — API endpoints + SPA frontend.
Монтируется в admin.py как отдельный APIRouter.
Доступен по: https://vadbag.su/app
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from config import BOT_TOKEN, get_level, get_next_level_threshold, LEVELS
import database as db

router = APIRouter()

# ─── Telegram initData verification ──────────────────────────────────────────

def verify_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Проверяет подлинность initData от Telegram WebApp.
    Возвращает dict с данными пользователя или None если невалидно.
    """
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        check_hash = parsed.pop("hash", None)
        if not check_hash:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # Telegram: secret_key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=BOT_TOKEN.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()

        # hash = HMAC-SHA256(secret_key, data_check_string)
        computed = hmac.new(
            key=secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed, check_hash):
            return None

        # Проверка свежести данных (не старше 24 часов)
        auth_date = int(parsed.get("auth_date", 0))
        if auth_date > 0 and time.time() - auth_date > 86400:
            return None

        user_json = parsed.get("user", "{}")
        return json.loads(user_json)
    except Exception as e:
        import sys
        print(f"[webapp] verify_telegram_init_data error: {e}", file=sys.stderr)
        return None


@router.get("/api/debug-auth")
async def debug_auth(request: Request):
    """Временный эндпоинт для отладки — удалить после исправления."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        init_data = request.query_params.get("initData", "")

    if not init_data:
        return JSONResponse({"step": "no_init_data"})

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    check_hash = parsed.pop("hash", None)

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()

    computed = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    auth_date = int(parsed.get("auth_date", 0))
    age_sec = int(time.time() - auth_date)

    return JSONResponse({
        "hash_match": computed == check_hash,
        "computed": computed[:16] + "...",
        "expected": (check_hash or "")[:16] + "...",
        "auth_date": auth_date,
        "age_seconds": age_sec,
        "bot_token_len": len(BOT_TOKEN),
        "bot_token_prefix": BOT_TOKEN[:8] + "...",
        "fields": list(parsed.keys()),
        "data_check_string_preview": data_check_string[:80],
    })


async def get_webapp_user(request: Request) -> dict:
    """Получить пользователя из initData заголовка."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        # Fallback: читаем из query param (для dev)
        init_data = request.query_params.get("initData", "")

    tg_user = verify_telegram_init_data(init_data)
    if not tg_user:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth")

    user = await db.get_user(tg_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not registered. Please start the bot first.")

    return user


# ─── API endpoints ────────────────────────────────────────────────────────────

@router.get("/api/me")
async def api_me(request: Request):
    """Профиль текущего пользователя."""
    user = await get_webapp_user(request)
    level_num, level_name = get_level(user["points_balance"])
    next_threshold = get_next_level_threshold(user["points_balance"])
    trigger_count = await db.count_triggers_total(user["id"])
    weekly = await db.get_weekly_stats(user["id"])
    return JSONResponse({
        "id": user["id"],
        "telegram_id": user["telegram_id"],
        "first_name": user["first_name"],
        "username": user["username"],
        "points": user["points_balance"],
        "xp": user["xp_balance"],
        "streak": user["streak_days"],
        "level_num": level_num,
        "level_name": level_name,
        "next_threshold": next_threshold,
        "trigger_count": trigger_count,
        "referral_code": user["referral_code"],
        "weekly": weekly,
    })


@router.get("/api/triggers")
async def api_triggers(request: Request, limit: int = 10, offset: int = 0):
    user = await get_webapp_user(request)
    triggers = await db.get_triggers(user["id"], limit=limit, offset=offset)
    patterns = await db.get_trigger_patterns(user["id"])
    return JSONResponse({"triggers": triggers, "patterns": patterns})


@router.get("/api/diary")
async def api_diary(request: Request, limit: int = 7):
    user = await get_webapp_user(request)
    entries = await db.get_diary_entries(user["id"], limit=limit)
    today_done = await db.check_diary_today(user["id"])
    return JSONResponse({"entries": entries, "today_done": today_done})


@router.get("/api/tasks")
async def api_tasks(request: Request):
    user = await get_webapp_user(request)
    tasks = await db.get_tasks(user["id"])
    return JSONResponse({"tasks": tasks})


@router.post("/api/tasks/{task_id}/complete")
async def api_complete_task(task_id: int, request: Request):
    user = await get_webapp_user(request)
    task = await db.get_task(task_id)
    if not task or task["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] == "done":
        raise HTTPException(status_code=400, detail="Already completed")
    result = await db.complete_task(task_id, user["telegram_id"])
    return JSONResponse(result)


@router.get("/api/shop")
async def api_shop(request: Request):
    user = await get_webapp_user(request)
    products = await db.get_products()
    purchases = await db.get_user_purchases(user["id"])
    bought_ids = {p["product_id"] for p in purchases}
    return JSONResponse({
        "products": products,
        "balance": user["points_balance"],
        "bought_ids": list(bought_ids),
    })


@router.post("/api/shop/{product_id}/buy")
async def api_buy(product_id: int, request: Request):
    user = await get_webapp_user(request)
    result = await db.buy_product(user["telegram_id"], product_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "error"))
    return JSONResponse(result)


@router.get("/api/patterns")
async def api_patterns(request: Request):
    user = await get_webapp_user(request)
    patterns = await db.get_trigger_patterns(user["id"])
    return JSONResponse(patterns)


# ─── SPA HTML ─────────────────────────────────────────────────────────────────

SPA_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>MindGame</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root {
    --bg: #0F0A1E;
    --bg2: #1A1030;
    --card: #231845;
    --card2: #2D1F5E;
    --accent: #7C3AED;
    --accent2: #A855F7;
    --gold: #F59E0B;
    --text: #F3F4F6;
    --muted: #9CA3AF;
    --green: #10B981;
    --red: #EF4444;
    --radius: 16px;
    --tab-h: 64px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; overflow: hidden; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

  /* Layout */
  #app { display: flex; flex-direction: column; height: 100vh; }
  #content { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 16px 16px calc(var(--tab-h) + 16px); }

  /* Tab bar */
  #tabs { position: fixed; bottom: 0; left: 0; right: 0; height: var(--tab-h); background: var(--bg2); border-top: 1px solid rgba(124,58,237,0.3); display: flex; z-index: 100; padding-bottom: env(safe-area-inset-bottom); }
  .tab { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; cursor: pointer; color: var(--muted); transition: color .2s; border: none; background: none; }
  .tab.active { color: var(--accent2); }
  .tab svg { width: 22px; height: 22px; }
  .tab span { font-size: 10px; font-weight: 500; }

  /* Cards */
  .card { background: var(--card); border-radius: var(--radius); padding: 16px; margin-bottom: 12px; }
  .card-title { font-size: 13px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }

  /* Header */
  .page-title { font-size: 22px; font-weight: 800; margin-bottom: 16px; }

  /* Stats grid */
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }
  .stat { background: var(--card2); border-radius: 12px; padding: 12px 8px; text-align: center; }
  .stat-v { font-size: 22px; font-weight: 800; color: var(--accent2); }
  .stat-l { font-size: 11px; color: var(--muted); margin-top: 2px; }

  /* Progress bar */
  .progress-wrap { margin: 8px 0 4px; }
  .progress-label { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-bottom: 5px; }
  .progress-bar { height: 6px; background: var(--bg); border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 3px; transition: width .5s; }

  /* Trigger list */
  .trigger-item { background: var(--card2); border-radius: 12px; padding: 12px; margin-bottom: 8px; }
  .trigger-text { font-size: 14px; line-height: 1.4; margin-bottom: 6px; }
  .trigger-meta { display: flex; gap: 6px; flex-wrap: wrap; }
  .badge { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .badge-purple { background: rgba(124,58,237,0.25); color: var(--accent2); }
  .badge-green { background: rgba(16,185,129,0.2); color: var(--green); }
  .badge-gold { background: rgba(245,158,11,0.2); color: var(--gold); }
  .badge-red { background: rgba(239,68,68,0.2); color: var(--red); }
  .badge-gray { background: rgba(156,163,175,0.15); color: var(--muted); }

  /* Diary */
  .diary-item { background: var(--card2); border-radius: 12px; padding: 14px; margin-bottom: 8px; }
  .diary-date { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .diary-body { font-size: 14px; line-height: 1.5; color: var(--text); }

  /* Tasks */
  .task-item { background: var(--card2); border-radius: 12px; padding: 14px; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 12px; }
  .task-check { width: 22px; height: 22px; border-radius: 6px; border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; margin-top: 1px; transition: all .2s; }
  .task-check.done { background: var(--accent); border-color: var(--accent); }
  .task-check.done::after { content: '✓'; color: white; font-size: 13px; font-weight: 700; }
  .task-info { flex: 1; }
  .task-title { font-size: 14px; line-height: 1.4; }
  .task-title.done { text-decoration: line-through; color: var(--muted); }
  .task-pts { font-size: 12px; color: var(--gold); margin-top: 3px; }

  /* Shop */
  .product-card { background: var(--card2); border-radius: 14px; padding: 16px; margin-bottom: 10px; display: flex; gap: 14px; align-items: flex-start; }
  .product-emoji { font-size: 36px; flex-shrink: 0; width: 50px; text-align: center; }
  .product-info { flex: 1; }
  .product-title { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
  .product-desc { font-size: 13px; color: var(--muted); line-height: 1.4; margin-bottom: 10px; }
  .product-footer { display: flex; align-items: center; justify-content: space-between; }
  .product-price { font-size: 16px; font-weight: 800; color: var(--gold); }
  .btn { display: inline-flex; align-items: center; justify-content: center; padding: 8px 18px; border-radius: 10px; font-size: 14px; font-weight: 700; border: none; cursor: pointer; transition: all .2s; }
  .btn-buy { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; }
  .btn-buy:disabled { opacity: .5; cursor: not-allowed; }
  .btn-bought { background: var(--green); color: white; }

  /* Patterns */
  .pattern-bar-wrap { margin-bottom: 6px; }
  .pattern-bar-label { display: flex; justify-content: space-between; font-size: 13px; color: var(--text); margin-bottom: 3px; }
  .pattern-bar { height: 8px; background: var(--bg); border-radius: 4px; overflow: hidden; }
  .pattern-bar-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 4px; }

  /* Loading / Empty */
  .loading { text-align: center; padding: 40px; color: var(--muted); }
  .empty { text-align: center; padding: 40px 20px; color: var(--muted); }
  .empty-icon { font-size: 48px; margin-bottom: 12px; }
  .empty-text { font-size: 15px; }
  .empty-hint { font-size: 13px; margin-top: 6px; }

  /* Level badge */
  .level-badge { display: inline-flex; align-items: center; gap: 6px; background: linear-gradient(135deg, var(--accent), var(--accent2)); padding: 5px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }

  /* Avatar */
  .avatar { width: 64px; height: 64px; border-radius: 50%; background: linear-gradient(135deg, var(--accent), var(--accent2)); display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; flex-shrink: 0; }

  /* Section tab pills */
  .pills { display: flex; gap: 8px; margin-bottom: 14px; overflow-x: auto; padding-bottom: 2px; }
  .pill { padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: none; cursor: pointer; white-space: nowrap; }
  .pill.active { background: var(--accent); color: white; }
  .pill:not(.active) { background: var(--card2); color: var(--muted); }

  /* Toast */
  #toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%) translateY(-80px); background: #1a1a2e; border: 1px solid var(--accent); color: var(--text); padding: 10px 20px; border-radius: 12px; font-size: 14px; font-weight: 600; z-index: 999; transition: transform .3s; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
  #toast.show { transform: translateX(-50%) translateY(0); }

  .text-muted { color: var(--muted); font-size: 13px; }
  .mt-4 { margin-top: 4px; }
  .mt-8 { margin-top: 8px; }
  .mt-12 { margin-top: 12px; }
  .row { display: flex; align-items: center; gap: 10px; }
  .col { display: flex; flex-direction: column; gap: 4px; }
</style>
</head>
<body>
<div id="app">
  <div id="content"></div>
  <nav id="tabs">
    <button class="tab active" data-tab="profile" onclick="showTab('profile')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
      <span>Профиль</span>
    </button>
    <button class="tab" data-tab="triggers" onclick="showTab('triggers')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      <span>Триггеры</span>
    </button>
    <button class="tab" data-tab="diary" onclick="showTab('diary')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h10M7 16h6"/></svg>
      <span>Дневник</span>
    </button>
    <button class="tab" data-tab="tasks" onclick="showTab('tasks')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
      <span>Задачи</span>
    </button>
    <button class="tab" data-tab="shop" onclick="showTab('shop')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
      <span>Магазин</span>
    </button>
  </nav>
</div>
<div id="toast"></div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();

// Раскрыть на полный экран (с повтором для надёжности)
tg.expand();
setTimeout(() => tg.expand(), 100);
setTimeout(() => tg.expand(), 500);

// Подтверждение закрытия
tg.enableClosingConfirmation();

// Главная кнопка (скрыта по умолчанию)
tg.MainButton.setParams({ text: "Продолжить", is_visible: false });

// Настроить viewport для полного экрана
const viewport = document.querySelector('meta[name=viewport]');
if (viewport) {
  viewport.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover');
}

// Установить цвета темы
if (tg.colorScheme) {
  document.documentElement.style.setProperty('--tg-theme', tg.colorScheme);
}

// Apply Telegram theme colors
if (tg.colorScheme === 'dark' || true) {
  document.documentElement.style.setProperty('--bg', '#0F0A1E');
}

const initData = tg.initData || '';
let currentTab = 'profile';
let cache = {};

// ─── API helper ───────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Ошибка');
  }
  return res.json();
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function toast(msg, duration = 2500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), duration);
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function showTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  render();
}

// ─── Render ───────────────────────────────────────────────────────────────────
const NO_INIT_DATA_HTML = `
  <div style="padding:40px 24px;text-align:center">
    <div style="font-size:60px;margin-bottom:20px">🤖</div>
    <div style="font-size:20px;font-weight:800;color:white;margin-bottom:12px">Открой через кнопку в боте</div>
    <div style="font-size:14px;color:var(--muted);line-height:1.6;margin-bottom:28px">
      Это приложение работает только как Telegram Mini App.<br>
      Оно НЕ открывается напрямую через браузер или ссылку.
    </div>
    <div style="background:var(--card2);border-radius:16px;padding:20px;text-align:left;margin-bottom:20px">
      <div style="font-size:13px;font-weight:700;color:var(--accent2);margin-bottom:12px">Как открыть:</div>
      <div style="font-size:14px;color:var(--text);line-height:2">
        1️⃣ Открой бота <b>@Vadimbagautdinov_bot</b><br>
        2️⃣ Отправь команду <b>/start</b><br>
        3️⃣ Нажми кнопку <b>🎮 Открыть приложение</b> под сообщением<br>
        &nbsp;&nbsp;&nbsp;&nbsp;или кнопку <b>🎮 Приложение</b> рядом с полем ввода
      </div>
    </div>
    <a href="https://t.me/Vadimbagautdinov_bot" style="display:inline-block;background:linear-gradient(135deg,#7C3AED,#A855F7);color:white;padding:14px 28px;border-radius:12px;font-size:15px;font-weight:700;text-decoration:none">
      Открыть бота →
    </a>
  </div>`;

async function render() {
  const content = document.getElementById('content');
  // Guard: if initData is missing, always show "open via bot" — never show API errors
  if (!initData) {
    content.innerHTML = NO_INIT_DATA_HTML;
    return;
  }
  content.innerHTML = '<div class="loading">Загрузка...</div>';
  try {
    if (currentTab === 'profile') await renderProfile(content);
    else if (currentTab === 'triggers') await renderTriggers(content);
    else if (currentTab === 'diary') await renderDiary(content);
    else if (currentTab === 'tasks') await renderTasks(content);
    else if (currentTab === 'shop') await renderShop(content);
  } catch (e) {
    const isAuthError = e.message && (e.message.includes('auth') || e.message.includes('401'));
    // If auth error — show "open via bot" message instead of raw error
    if (isAuthError) {
      content.innerHTML = NO_INIT_DATA_HTML;
      return;
    }
    content.innerHTML = `
      <div class="empty">
        <div class="empty-icon">⚠️</div>
        <div class="empty-text">${e.message}</div>
        <div class="empty-hint">Попробуй закрыть и снова открыть приложение</div>
      </div>`;
  }
}

async function runDebug() {
  const out = document.getElementById('debug-out');
  if (!out) return;
  out.textContent = 'Запрос...';
  try {
    const r = await fetch('/api/debug-auth', {
      headers: { 'X-Telegram-Init-Data': initData }
    });
    const d = await r.json();
    out.textContent = JSON.stringify(d, null, 2);
  } catch(e) {
    out.textContent = 'Ошибка: ' + e.message;
  }
}

// ─── Profile ──────────────────────────────────────────────────────────────────
async function renderProfile(el) {
  const data = await api('/api/me');
  const progress = data.next_threshold
    ? Math.round((data.points / data.next_threshold) * 100)
    : 100;

  const name = data.first_name || 'Игрок';
  const emoji_levels = ['👁','🔍','🧘','🎮','✨'];
  const lvl_emoji = emoji_levels[Math.min(data.level_num - 1, 4)];
  
  // Получаем аватар из Telegram
  const userAvatar = tg.initDataUnsafe?.user?.photo_url || null;

  el.innerHTML = `
    <div class="page-title">Мой профиль</div>
    <div class="card">
      <div class="row" style="margin-bottom:14px">
        ${userAvatar 
          ? `<img src="${userAvatar}" alt="Avatar" style="width:64px;height:64px;border-radius:50%;object-fit:cover;flex-shrink:0">`
          : `<div class="avatar">${name[0].toUpperCase()}</div>`
        }
        <div class="col">
          <div style="font-size:18px;font-weight:700">${name}</div>
          ${data.username ? `<div class="text-muted">@${data.username}</div>` : ''}
          <div class="mt-4"><span class="level-badge">${lvl_emoji} ${data.level_name}</span></div>
        </div>
      </div>
      <div class="progress-wrap">
        <div class="progress-label">
          <span>⭐ ${data.points} очков</span>
          <span>${data.next_threshold ? `до ур. ${data.level_num + 1}: ${data.next_threshold}` : 'Максимальный уровень!'}</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:${progress}%"></div></div>
      </div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="stat-v">${data.trigger_count}</div>
        <div class="stat-l">Триггеров</div>
      </div>
      <div class="stat">
        <div class="stat-v">${data.streak}</div>
        <div class="stat-l">Дней стрик</div>
      </div>
      <div class="stat">
        <div class="stat-v">${data.weekly.points || 0}</div>
        <div class="stat-l">Очков/нед</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">За эту неделю</div>
      <div style="display:flex;justify-content:space-around;text-align:center">
        <div>
          <div style="font-size:24px;font-weight:800;color:#A855F7">${data.weekly.triggers}</div>
          <div class="text-muted">триггеров</div>
        </div>
        <div>
          <div style="font-size:24px;font-weight:800;color:#10B981">${data.weekly.diary}</div>
          <div class="text-muted">записей</div>
        </div>
        <div>
          <div style="font-size:24px;font-weight:800;color:#F59E0B">${data.weekly.points}</div>
          <div class="text-muted">очков</div>
        </div>
      </div>
    </div>

    ${data.referral_code ? `
    <div class="card">
      <div class="card-title">Реферальный код</div>
      <div style="display:flex;align-items:center;gap:10px">
        <div style="flex:1;background:var(--bg);border-radius:10px;padding:10px 14px;font-size:16px;font-weight:700;letter-spacing:.1em;font-family:monospace;cursor:pointer" onclick="copyRefLink('${data.referral_code}')">${data.referral_code}</div>
        <button class="btn btn-buy" style="padding:10px 14px" onclick="copyRefLink('${data.referral_code}')">Копировать</button>
      </div>
      <div class="text-muted mt-8">Приглашай друзей и получай по 50 очков за каждого!</div>
    </div>` : ''}
  `;
}

function copyRefLink(code) {
  // Копируем полную ссылку на бота
  const botUsername = 'Vadimbagautdinov_bot'; // Можно получить из API если нужно
  const link = `https://t.me/${botUsername}?start=${code}`;
  
  if (navigator.clipboard) {
    navigator.clipboard.writeText(link).then(() => {
      toast('✅ Ссылка скопирована!');
      // Haptic feedback
      if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
      }
    }).catch(() => {
      fallbackCopy(link);
    });
  } else {
    fallbackCopy(link);
  }
}

function fallbackCopy(text) {
  // Fallback для старых браузеров
  tg.switchInlineQuery(`Привет! Присоединяйся к MindGame — игре для осознанности: ${text}`);
}

// ─── Triggers ─────────────────────────────────────────────────────────────────
const EMOTIONS = {
  anger:'😡 Злость', fear:'😨 Страх', sadness:'😢 Грусть',
  joy:'😄 Радость', disgust:'🤢 Отвращение', shame:'😳 Стыд',
  anxiety:'😰 Тревога', surprise:'😮 Удивление', guilt:'😞 Вина',
  love:'❤️ Любовь', envy:'💚 Зависть', pride:'💪 Гордость',
};

function emotionBadge(code) {
  return code ? `<span class="badge badge-purple">${EMOTIONS[code] || code}</span>` : '';
}
function intensityBadge(i) {
  if (!i) return '';
  const cls = i >= 8 ? 'badge-red' : i >= 5 ? 'badge-gold' : 'badge-green';
  return `<span class="badge ${cls}">🔥 ${i}/10</span>`;
}

async function renderTriggers(el) {
  const data = await api('/api/triggers?limit=20');
  const triggers = data.triggers;
  const patterns = data.patterns;

  let html = `<div class="page-title">Триггеры</div>`;

  // Patterns summary
  if (patterns.top_emotions?.length > 0) {
    const max = patterns.top_emotions[0].count;
    html += `<div class="card">
      <div class="card-title">Топ эмоций (всего ${patterns.total})</div>
      ${patterns.top_emotions.map(e => `
        <div class="pattern-bar-wrap">
          <div class="pattern-bar-label"><span>${EMOTIONS[e.emotion] || e.emotion}</span><span>${e.count}</span></div>
          <div class="pattern-bar"><div class="pattern-bar-fill" style="width:${Math.round(e.count/max*100)}%"></div></div>
        </div>
      `).join('')}
    </div>`;
  }

  if (!triggers.length) {
    html += `<div class="empty"><div class="empty-icon">⚡</div><div class="empty-text">Пока нет триггеров</div><div class="empty-hint">Запиши первый триггер через бот</div></div>`;
  } else {
    html += triggers.map(t => `
      <div class="trigger-item">
        <div class="trigger-text">${escHtml(t.raw_text || '')}</div>
        <div class="trigger-meta">
          ${emotionBadge(t.emotion_code)}
          ${intensityBadge(t.intensity)}
          ${t.category_code ? `<span class="badge badge-gray">${t.category_code}</span>` : ''}
          ${t.points_awarded ? `<span class="badge badge-green">+${t.points_awarded}⭐</span>` : ''}
          <span class="badge badge-gray">${fmtDate(t.created_at)}</span>
        </div>
        ${t.insight_text ? `<div style="margin-top:8px;font-size:13px;color:var(--muted);font-style:italic">💡 ${escHtml(t.insight_text)}</div>` : ''}
      </div>
    `).join('');
  }
  el.innerHTML = html;
}

// ─── Diary ───────────────────────────────────────────────────────────────────
const MOODS = { great:'😄 Отлично', good:'🙂 Хорошо', neutral:'😐 Нейтрально', bad:'😔 Плохо', awful:'😢 Ужасно' };

async function renderDiary(el) {
  const data = await api('/api/diary?limit=14');
  const entries = data.entries;

  let html = `<div class="page-title">Дневник</div>`;

  if (data.today_done) {
    html += `<div class="card" style="border:1px solid rgba(16,185,129,0.4)"><div style="display:flex;align-items:center;gap:10px"><span style="font-size:24px">✅</span><div><div style="font-weight:700">Сегодня уже записано!</div><div class="text-muted">Отличная работа</div></div></div></div>`;
  } else {
    html += `<div class="card" style="border:1px solid rgba(124,58,237,0.4)"><div style="display:flex;align-items:center;gap:10px"><span style="font-size:24px">📔</span><div><div style="font-weight:700">Дневник ждёт</div><div class="text-muted">Запиши мысли за сегодня через бот</div></div></div></div>`;
  }

  if (!entries.length) {
    html += `<div class="empty"><div class="empty-icon">📔</div><div class="empty-text">Дневник пуст</div><div class="empty-hint">Начни писать через бота каждый день</div></div>`;
  } else {
    html += entries.map(e => `
      <div class="diary-item">
        <div class="diary-date">
          ${fmtDate(e.created_at)}
          ${e.mood_code ? `&nbsp;·&nbsp;${MOODS[e.mood_code] || e.mood_code}` : ''}
          ${e.energy_level ? `&nbsp;·&nbsp;⚡${e.energy_level}/10` : ''}
          ${e.points_awarded ? `&nbsp;·&nbsp;<span style="color:var(--gold)">+${e.points_awarded}⭐</span>` : ''}
        </div>
        <div class="diary-body">${escHtml(e.body || '')}</div>
        ${e.insight_text ? `<div style="margin-top:8px;font-size:13px;color:var(--muted);font-style:italic">💡 ${escHtml(e.insight_text)}</div>` : ''}
      </div>
    `).join('');
  }
  el.innerHTML = html;
}

// ─── Tasks ────────────────────────────────────────────────────────────────────
const DIFF_LABELS = { easy:'☀️ Лёгкая', medium:'🌤 Средняя', hard:'⚡ Сложная', uncomfortable:'🔥 Дискомфорт' };

async function renderTasks(el) {
  const data = await api('/api/tasks');
  const tasks = data.tasks;

  const active = tasks.filter(t => t.status !== 'done');
  const done = tasks.filter(t => t.status === 'done');

  let html = `<div class="page-title">Задачи</div>`;

  if (!tasks.length) {
    html += `<div class="empty"><div class="empty-icon">✅</div><div class="empty-text">Нет задач</div><div class="empty-hint">Добавь задачи через бота командой /tasks</div></div>`;
  } else {
    if (active.length) {
      html += `<div class="card-title" style="margin-bottom:8px">Активные (${active.length})</div>`;
      html += active.map(t => taskHtml(t)).join('');
    }
    if (done.length) {
      html += `<div class="card-title" style="margin:16px 0 8px">Выполнено (${done.length})</div>`;
      html += done.map(t => taskHtml(t)).join('');
    }
  }
  el.innerHTML = html;
}

function taskHtml(t) {
  const isDone = t.status === 'done';
  return `
    <div class="task-item" id="task-${t.id}">
      <div class="task-check ${isDone ? 'done' : ''}" ${!isDone ? `onclick="completeTask(${t.id})"` : ''}></div>
      <div class="task-info">
        <div class="task-title ${isDone ? 'done' : ''}">${escHtml(t.title)}</div>
        <div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">
          <span class="badge badge-purple">${DIFF_LABELS[t.estimated_difficulty_score] || t.estimated_difficulty_score}</span>
          <span class="badge badge-gold">+${isDone ? t.points_awarded : t.estimated_points}⭐</span>
        </div>
      </div>
    </div>
  `;
}

async function completeTask(taskId) {
  try {
    const result = await api(`/api/tasks/${taskId}/complete`, { method: 'POST' });
    tg.HapticFeedback?.notificationOccurred('success');
    toast(`✅ +${result.points} очков!`);
    await renderTasks(document.getElementById('content'));
  } catch (e) {
    toast('❌ ' + e.message);
  }
}

// ─── Shop ─────────────────────────────────────────────────────────────────────
const CAT_EMOJI = { digital:'📱', consultation:'📞', course:'📚', physical:'🎁' };

async function renderShop(el) {
  const data = await api('/api/shop');
  const products = data.products;
  const balance = data.balance;
  const bought = new Set(data.bought_ids);

  let html = `
    <div class="page-title">Магазин</div>
    <div class="card" style="margin-bottom:14px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <div style="font-size:13px;color:var(--muted)">Твой баланс</div>
          <div style="font-size:28px;font-weight:800;color:var(--gold)">⭐ ${balance}</div>
        </div>
        <div style="font-size:40px">🛍️</div>
      </div>
    </div>
  `;

  if (!products.length) {
    html += `<div class="empty"><div class="empty-icon">🛒</div><div class="empty-text">Магазин пуст</div></div>`;
  } else {
    html += products.map(p => {
      const isBought = bought.has(p.id);
      const canBuy = balance >= p.price_points && !isBought;
      const emojiRe = new RegExp("^[\\u{1F300}-\\u{1FAFF}\\u{2600}-\\u{27BF}]", "u");
  const emoji = emojiRe.exec(p.title)?.[0] || CAT_EMOJI[p.category] || '🎁';
      return `
        <div class="product-card">
          <div class="product-emoji">${emoji}</div>
          <div class="product-info">
            <div class="product-title">${escHtml(p.title)}</div>
            <div class="product-desc">${escHtml(p.description || '')}</div>
            <div class="product-footer">
              <div class="product-price">⭐ ${p.price_points}</div>
              ${isBought
                ? `<button class="btn btn-bought" disabled>✓ Куплено</button>`
                : `<button class="btn btn-buy" ${!canBuy ? 'disabled' : ''} onclick="buyProduct(${p.id}, '${escHtml(p.title)}')">${canBuy ? 'Купить' : `Нужно ${p.price_points - balance} ⭐`}</button>`
              }
            </div>
          </div>
        </div>
      `;
    }).join('');
  }
  el.innerHTML = html;
}

async function buyProduct(productId, title) {
  if (!confirm(`Купить «${title}»?`)) return;
  try {
    const result = await api(`/api/shop/${productId}/buy`, { method: 'POST' });
    tg.HapticFeedback?.notificationOccurred('success');
    toast(`✅ Куплено! Баланс: ${result.balance} ⭐`);
    await renderShop(document.getElementById('content'));
  } catch (e) {
    toast('❌ ' + e.message);
  }
}

// ─── Utils ────────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ','T') + 'Z');
  return d.toLocaleDateString('ru-RU', { day:'numeric', month:'short' });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
if (!initData) {
  document.getElementById('content').innerHTML = NO_INIT_DATA_HTML;
} else {
  render();
}
</script>
</body>
</html>
"""


@router.get("/app", response_class=HTMLResponse)
async def webapp_spa(request: Request):
    """Точка входа в Telegram Mini App."""
    return HTMLResponse(content=SPA_HTML)
