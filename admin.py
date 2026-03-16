"""
Admin web panel — запуск: python3 admin.py
Лендинг:    http://localhost:8080/
Вход:       http://localhost:8080/login
Дашборд:    http://localhost:8080/admin
"""
import asyncio
import aiohttp
from datetime import datetime, date
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import aiosqlite
import uvicorn

from config import DB_PATH, BOT_TOKEN, get_level, LEVELS, ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_SECRET
from webapp import router as webapp_router
import database as db


# ─── Broadcasts DB init ───────────────────────────────────────────────────────

async def init_broadcasts_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_role TEXT NOT NULL,
                message_text TEXT NOT NULL,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT
            )
        """)
        await db.commit()


@asynccontextmanager
async def lifespan(app):
    await init_broadcasts_table()
    yield


app = FastAPI(title="Admin Panel", lifespan=lifespan)

# Mount Telegram Mini App router
app.include_router(webapp_router)

# ─── Auth middleware ───────────────────────────────────────────────────────────
# IMPORTANT: add_middleware wraps in reverse — last added runs first.
# SessionMiddleware must be outermost (last added), AuthMiddleware inner.

PUBLIC_PATHS = {"/", "/login", "/app"}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # /app and /api/* are protected by Telegram initData — skip admin auth
        if path not in PUBLIC_PATHS and not path.startswith("/api/"):
            if not request.session.get("authenticated"):
                return RedirectResponse("/login", status_code=302)
        return await call_next(request)

app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="admin_session")


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def db_fetchall(query: str, params=()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def db_fetchone(query: str, params=()) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def db_execute(query: str, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


def level_badge(xp: int) -> str:
    level_num, level_name = get_level(xp)
    colors = ["#6B7280", "#3B82F6", "#8B5CF6", "#F59E0B", "#EF4444"]
    color = colors[min(level_num - 1, 4)]
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:12px">Ур.{level_num} {level_name}</span>'


def fmt_date(date_str: str, short: bool = False) -> str:
    """Форматирует дату из БД в формат ДД.ММ.ГГ или ДД.ММ.ГГ ЧЧ:ММ."""
    if not date_str:
        return "—"
    try:
        # Формат БД: 2026-03-10 14:30:00
        if " " in date_str:
            date_part, time_part = date_str.split(" ")
            year, month, day = date_part.split("-")
            hour, minute = time_part.split(":")[:2]
            if short:
                return f"{day}.{month}.{year[2:]}"
            return f"{day}.{month}.{year[2:]} {hour}:{minute}"
        else:
            year, month, day = date_str.split("-")
            return f"{day}.{month}.{year[2:]}"
    except Exception:
        return date_str[:10] if short else date_str[:16]


def page(title: str, content: str, active: str = "") -> str:
    from config import IS_TEST_ENV
    
    # Визуальный индикатор тестовой зоны
    test_banner = ""
    if IS_TEST_ENV:
        test_banner = '''
        <div style="background:#EF4444;color:white;text-align:center;padding:8px;font-weight:700;font-size:14px;">
            ⚠️ ТЕСТОВАЯ ЗОНА — данные не настоящие
        </div>
        '''
    
    # Изменить цвет сайдбара для тестовой зоны
    sidebar_bg = "#111827" if not IS_TEST_ENV else "#7C1D1D"
    
    nav_items = [
        ("📊 Дашборд", "/admin", "dashboard"),
        ("👥 Пользователи", "/users", "users"),
        ("📝 Триггеры", "/triggers", "triggers"),
        ("📔 Дневник", "/diary", "diary"),
        ("🏆 Достижения", "/achievements", "achievements"),
        ("📢 Рассылки", "/broadcasts", "broadcasts"),
        ("💬 Поддержка", "/support", "messages"),
        ("👥 Рефералы", "/referrals", "referrals"),
        ("⭐ Очки", "/points", "points"),
        ("🎛 Меню бота", "/menu", "menu"),
    ]
    nav_html = ""
    for label, href, key in nav_items:
        is_active = "background:#1F2937;color:white;" if key == active else "color:#9CA3AF;"
        nav_html += f'<a href="{href}" style="display:block;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:14px;{is_active}">{label}</a>'
    nav_html += '<a href="/logout" style="display:block;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:14px;color:#EF4444;margin-top:16px;border-top:1px solid #374151;padding-top:16px">🚪 Выйти</a>'

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — Admin {"(TEST)" if IS_TEST_ENV else ""}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F9FAFB;color:#111827}}
    .layout{{display:flex;min-height:100vh}}
    .sidebar{{width:220px;background:{sidebar_bg};padding:20px 12px;flex-shrink:0}}
    .sidebar h1{{color:white;font-size:16px;font-weight:700;margin-bottom:24px;padding:0 4px}}
    .main{{flex:1;padding:24px;overflow:auto}}
    h2{{font-size:20px;font-weight:700;margin-bottom:20px;color:#111827}}
    .card{{background:white;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:16px}}
    .stats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-bottom:24px}}
    .stat{{background:white;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1);text-align:center}}
    .stat-value{{font-size:32px;font-weight:800;color:#1F2937}}
    .stat-label{{font-size:13px;color:#6B7280;margin-top:4px}}
    table{{width:100%;border-collapse:collapse;font-size:14px}}
    th{{text-align:left;padding:10px 12px;background:#F3F4F6;color:#6B7280;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
    td{{padding:10px 12px;border-bottom:1px solid #F3F4F6;vertical-align:middle}}
    tr:hover td{{background:#F9FAFB}}
    a{{color:#3B82F6;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .btn{{display:inline-block;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none}}
    .btn-blue{{background:#3B82F6;color:white}}
    .btn-red{{background:#EF4444;color:white}}
    .btn-green{{background:#10B981;color:white}}
    input,select{{padding:8px 12px;border:1px solid #D1D5DB;border-radius:8px;font-size:14px;outline:none}}
    input:focus{{border-color:#3B82F6}}
    .badge{{padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}}
    .badge-green{{background:#D1FAE5;color:#065F46}}
    .badge-gray{{background:#F3F4F6;color:#374151}}
    .tag{{display:inline-block;background:#EEF2FF;color:#4338CA;padding:2px 8px;border-radius:6px;font-size:12px;margin:2px}}
    .trigger-text{{max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    form.inline{{display:inline}}
  </style>
</head>
<body>
{test_banner}
<div class="layout">
  <div class="sidebar">
    <h1>🎮 Admin Panel {"🧪 TEST" if IS_TEST_ENV else ""}</h1>
    {nav_html}
  </div>
  <div class="main">
    <h2>{title}</h2>
    {content}
  </div>
</div>
</body>
</html>"""


# ─── Landing page ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/admin", status_code=302)
    return HTMLResponse(LANDING_HTML)


LANDING_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MindGame — Твой персональный тренер осознанности с AI</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{
      --primary:#8B5CF6;--primary-light:#A78BFA;--primary-dark:#7C3AED;
      --accent:#06B6D4;--accent2:#22D3EE;
      --dark:#0A0A0F;--dark-2:#12121A;--card:#161622;
      --text:#F1F5F9;--text-muted:#94A3B8;--border:#27273A;
      --success:#10B981;--warning:#F59E0B;--danger:#EF4444;
    }
    body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:var(--dark);color:var(--text);line-height:1.6;overflow-x:hidden}
    a{color:var(--primary-light);text-decoration:none;transition:.2s}
    a:hover{color:white}
    
    /* ANIMATIONS */
    @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
    @keyframes pulse-glow{0%,100%{box-shadow:0 0 20px rgba(139,92,246,.3)}50%{box-shadow:0 0 40px rgba(139,92,246,.5)}}
    @keyframes gradient{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
    
    /* NAV */
    nav{display:flex;justify-content:space-between;align-items:center;
        padding:16px 32px;position:sticky;top:0;z-index:1000;
        background:rgba(10,10,15,.9);backdrop-filter:blur(20px);
        border-bottom:1px solid var(--border)}
    .logo{font-size:22px;font-weight:800;color:white;letter-spacing:-.5px}
    .logo span{background:linear-gradient(135deg,var(--primary),var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .nav-btn{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:white;
             padding:10px 24px;border-radius:12px;font-size:14px;font-weight:600;
             transition:.3s;border:none;cursor:pointer}
    .nav-btn:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(139,92,246,.4)}
    
    /* HERO */
    .hero{position:relative;text-align:center;padding:120px 20px 80px;max-width:900px;margin:0 auto}
    .hero-tag{display:inline-flex;align-items:center;gap:8px;
              background:linear-gradient(135deg,rgba(139,92,246,.2),rgba(6,182,212,.2));
              border:1px solid rgba(139,92,246,.4);padding:8px 20px;border-radius:24px;
              font-size:13px;font-weight:600;margin-bottom:28px;letter-spacing:.05em;
              animation:float 3s ease-in-out infinite}
    .hero-tag::before{content:'🤖';font-size:16px}
    h1{font-size:clamp(42px,8vw,72px);font-weight:900;line-height:1.05;
       color:white;margin-bottom:24px;letter-spacing:-.03em}
    h1 span{background:linear-gradient(135deg,var(--primary-light),var(--accent2));
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            background-size:200% 200%;animation:gradient 5s ease infinite}
    .hero p{font-size:20px;color:var(--text-muted);max-width:600px;margin:0 auto 40px;line-height:1.7}
    .cta-group{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
    .btn-primary{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:white;
                 padding:18px 42px;border-radius:16px;font-size:17px;font-weight:700;
                 transition:.3s;box-shadow:0 4px 24px rgba(139,92,246,.4);border:none;cursor:pointer}
    .btn-primary:hover{transform:translateY(-3px);box-shadow:0 12px 40px rgba(139,92,246,.5)}
    .btn-secondary{background:rgba(255,255,255,.05);color:var(--text);padding:18px 42px;
                   border-radius:16px;font-size:17px;font-weight:600;
                   border:1.5px solid var(--border);transition:.3s;cursor:pointer}
    .btn-secondary:hover{border-color:var(--primary-light);background:rgba(139,92,246,.1)}
    
    /* STATS */
    .stats-bar{display:flex;justify-content:center;gap:32px;padding:48px 20px;
               border-top:1px solid var(--border);border-bottom:1px solid var(--border);
               flex-wrap:wrap;background:rgba(139,92,246,.03)}
    .stat{text-align:center;min-width:120px}
    .stat-num{font-size:42px;font-weight:900;background:linear-gradient(135deg,var(--primary-light),var(--accent2));
              -webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .stat-lbl{font-size:13px;color:var(--text-muted);margin-top:6px;font-weight:500;text-transform:uppercase;letter-spacing:.08em}
    
    /* SECTIONS */
    section{padding:100px 20px;max-width:1200px;margin:0 auto}
    .section-tag{text-align:center;display:inline-flex;align-items:center;gap:6px;
                 color:var(--primary-light);font-size:13px;font-weight:700;
                 letter-spacing:.15em;text-transform:uppercase;margin-bottom:16px;
                 background:rgba(139,92,246,.1);padding:6px 16px;border-radius:20px}
    h2{text-align:center;font-size:clamp(32px,5vw,52px);font-weight:800;
       color:white;margin-bottom:20px;letter-spacing:-.02em}
    .section-subtitle{text-align:center;font-size:18px;color:var(--text-muted);
                      max-width:600px;margin:0 auto 60px;line-height:1.7}
    
    /* FEATURES GRID */
    .features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:24px}
    .feature-card{position:relative;background:var(--card);border:1px solid var(--border);
                  border-radius:24px;padding:32px;transition:.3s;overflow:hidden}
    .feature-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
                          background:linear-gradient(90deg,var(--primary),var(--accent));opacity:0;transition:.3s}
    .feature-card:hover{transform:translateY(-6px);border-color:rgba(139,92,246,.4);
                        box-shadow:0 20px 60px rgba(0,0,0,.4)}
    .feature-card:hover::before{opacity:1}
    .feature-icon{font-size:44px;margin-bottom:20px;display:block}
    .feature-card h3{font-size:20px;font-weight:700;color:white;margin-bottom:12px}
    .feature-card p{font-size:15px;color:var(--text-muted);line-height:1.7}
    .feature-badge{display:inline-block;background:rgba(6,182,212,.15);color:var(--accent2);
                   padding:4px 12px;border-radius:8px;font-size:11px;font-weight:700;
                   margin-top:16px;text-transform:uppercase;letter-spacing:.08em}
    
    /* AI FEATURES */
    .ai-features{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:60px}
    .ai-card{background:linear-gradient(135deg,rgba(139,92,246,.1),rgba(6,182,212,.05));
             border:1px solid rgba(139,92,246,.3);border-radius:20px;padding:28px;
             text-align:center;transition:.3s}
    .ai-card:hover{transform:scale(1.02);border-color:var(--primary-light)}
    .ai-icon{font-size:36px;margin-bottom:16px}
    .ai-card h4{font-size:17px;font-weight:700;color:white;margin-bottom:8px}
    .ai-card p{font-size:14px;color:var(--text-muted)}
    
    /* HOW IT WORKS */
    .steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:40px}
    .step{text-align:center;position:relative}
    .step-num{width:64px;height:64px;background:linear-gradient(135deg,var(--primary),var(--accent));
              border-radius:20px;display:flex;align-items:center;justify-content:center;
              margin:0 auto 24px;font-size:26px;font-weight:800;color:white;
              box-shadow:0 8px 32px rgba(139,92,246,.4);animation:float 3s ease-in-out infinite}
    .step h3{font-size:19px;font-weight:700;color:white;margin-bottom:12px}
    .step p{font-size:15px;color:var(--text-muted);line-height:1.7}
    
    /* LEVELS */
    .levels{display:flex;flex-direction:column;gap:16px;max-width:700px;margin:0 auto}
    .level-row{display:flex;align-items:center;gap:20px;background:var(--card);
               border:1px solid var(--border);border-radius:18px;padding:20px 24px;
               transition:.3s}
    .level-row:hover{border-color:rgba(139,92,246,.4);transform:translateX(8px)}
    .level-icon{font-size:32px;flex-shrink:0}
    .level-info{flex:1}
    .level-name{font-weight:700;color:white;font-size:16px}
    .level-desc{font-size:13px;color:var(--text-muted);margin-top:4px}
    .level-xp{font-size:13px;color:var(--primary-light);font-weight:700;background:rgba(139,92,246,.15);
              padding:6px 14px;border-radius:10px}
    
    /* GAMIFICATION */
    .gamification-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;margin-top:50px}
    .gam-card{text-align:center;background:var(--card);border:1px solid var(--border);
              border-radius:20px;padding:28px;transition:.3s}
    .gam-card:hover{transform:translateY(-4px);border-color:var(--primary-light)}
    .gam-icon{font-size:40px;margin-bottom:16px}
    .gam-value{font-size:32px;font-weight:800;color:white;margin-bottom:8px}
    .gam-label{font-size:13px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em}
    
    /* TESTIMONIAL */
    .testimonial{background:linear-gradient(135deg,rgba(139,92,246,.1),rgba(6,182,212,.05));
                 border:1px solid rgba(139,92,246,.3);border-radius:24px;padding:40px;
                 text-align:center;max-width:800px;margin:0 auto}
    .testimonial-text{font-size:20px;color:var(--text);font-style:italic;line-height:1.8;margin-bottom:24px}
    .testimonial-author{color:var(--primary-light);font-weight:600}
    
    /* ADMIN LOGIN */
    .login-section{background:var(--card);border:1px solid var(--border);
                   border-radius:24px;max-width:440px;margin:0 auto;padding:48px 40px}
    .login-section h2{text-align:center;margin-bottom:32px;font-size:24px}
    .field{margin-bottom:20px}
    .field label{display:block;font-size:13px;font-weight:600;color:var(--text-muted);
                 margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
    .field input{width:100%;padding:14px 16px;background:var(--dark-2);color:white;
                 border:1.5px solid var(--border);border-radius:12px;font-size:15px;
                 outline:none;transition:.2s}
    .field input:focus{border-color:var(--primary-light)}
    .login-btn{width:100%;padding:15px;background:linear-gradient(135deg,var(--primary),var(--primary-dark));
               color:white;border:none;border-radius:12px;font-size:16px;font-weight:700;
               cursor:pointer;transition:.3s}
    .login-btn:hover{opacity:.9;transform:translateY(-2px)}
    .error-msg{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);
               color:#FCA5A5;padding:12px 16px;border-radius:10px;
               font-size:14px;margin-bottom:20px;text-align:center}
    
    /* FOOTER */
    footer{text-align:center;padding:48px 20px;color:var(--text-muted);font-size:14px;
           border-top:1px solid var(--border)}
    footer strong{color:var(--primary-light)}
    
    /* BG EFFECTS */
    .bg-glow{position:fixed;width:800px;height:800px;border-radius:50%;
              background:radial-gradient(circle,rgba(139,92,246,.08),transparent 60%);
              top:-300px;left:50%;transform:translateX(-50%);pointer-events:none;z-index:0}
    .bg-glow-2{position:fixed;width:600px;height:600px;border-radius:50%;
               background:radial-gradient(circle,rgba(6,182,212,.06),transparent 60%);
               bottom:-200px;right:-100px;pointer-events:none;z-index:0}
    
    /* RESPONSIVE */
    @media(max-width:768px){
      nav{padding:14px 20px}
      .hero{padding:80px 16px 60px}
      .stats-bar{gap:24px}
      .features-grid{grid-template-columns:1fr}
      .cta-group{flex-direction:column}
      .btn-primary,.btn-secondary{width:100%}
    }
  </style>
</head>
<body>
<div class="bg-glow"></div>
<div class="bg-glow-2"></div>

<!-- NAV -->
<nav>
  <div class="logo">Mind<span>Game</span></div>
  <a class="nav-btn" href="https://t.me/Vadimbagautdinov_bot" target="_blank">🚀 Запустить бота</a>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-tag">AI-powered тренер осознанности</div>
  <h1>Стань <span>автором</span><br>своей реальности</h1>
  <p>Первый Telegram-бот с глубоким AI-анализом триггеров, паттернов поведения и персональными инсайтами. Геймификация, которая превращает рост в увлекательную игру.</p>
  <div class="cta-group">
    <a class="btn-primary" href="https://t.me/Vadimbagautdinov_bot" target="_blank">🤖 Начать бесплатно</a>
    <a class="btn-secondary" href="#features">Узнать больше ↓</a>
  </div>
</div>

<!-- STATS -->
<div class="stats-bar">
  <div class="stat"><div class="stat-num">5</div><div class="stat-lbl">Уровней</div></div>
  <div class="stat"><div class="stat-num">12+</div><div class="stat-lbl">Фич</div></div>
  <div class="stat"><div class="stat-num">4</div><div class="stat-lbl">AI Модели</div></div>
  <div class="stat"><div class="stat-num">∞</div><div class="stat-lbl">Инсайтов</div></div>
</div>

<!-- FEATURES -->
<section id="features">
  <span class="section-tag">✨ Возможности</span>
  <h2>Всё для твоей трансформации</h2>
  <p class="section-subtitle">12 мощных инструментов для работы с сознанием, эмоциями и поведением</p>
  
  <div class="features-grid">
    <div class="feature-card">
      <span class="feature-icon">🧩</span>
      <h3>AI-анализ паттернов</h3>
      <p>Глубокий анализ твоих триггеров с выявлением скрытых связей. 3 уровня глубины: от поверхностных реакций к глубинным убеждениям.</p>
      <span class="feature-badge">🔥 Уникальная фича</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">📝</span>
      <h3>Дневник триггеров</h3>
      <p>Фиксируй ситуации, которые задевают. AI определяет эмоцию, категорию, помогает найти зону контроля и получить инсайт.</p>
      <span class="feature-badge">AI-powered</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">📔</span>
      <h3>Вечерний дневник</h3>
      <p>3 минуты рефлексии в день. Отслеживай настроение, энергию, напряжение. AI выделяет инсайты из записей.</p>
      <span class="feature-badge">Ежедневная практика</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">🛑</span>
      <h3>Стоп-режим</h3>
      <p>Экстренная помощь при сильных эмоциях. Дыхательные упражнения, оценка интенсивности, конкретные советы.</p>
      <span class="feature-badge">SOS-инструмент</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">🎤</span>
      <h3>Голосовые триггеры</h3>
      <p>Записывай триггеры голосом. Оффлайн-транскрибация через Vosk — приватно, быстро, без интернета.</p>
      <span class="feature-badge">Offline STT</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">✅</span>
      <h3>Задачи роста</h3>
      <p>Превращай страхи в действия. Дискомфортные задачи оцениваются выше. Преврати рост в игру с наградами.</p>
      <span class="feature-badge">Геймификация</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">🏆</span>
      <h3>Достижения</h3>
      <p>10+ достижений за серии дней, количество триггеров, глубину практики. Коллекционируй прогресс.</p>
      <span class="feature-badge">Collection</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">🛍</span>
      <h3>Магазин наград</h3>
      <p>Трать TRGR на консультации, курсы, материалы. Реальные награды за реальные изменения.</p>
      <span class="feature-badge">Rewards</span>
    </div>

    <div class="feature-card">
      <span class="feature-icon">📊</span>
      <h3>Недельные отчёты</h3>
      <p>Автоматическая сводка каждую неделю: триггеры, записи, TRGR, серии. Видимый прогресс.</p>
      <span class="feature-badge">Auto-analytics</span>
    </div>

    <div class="feature-card">
      <span class="feature-icon">👥</span>
      <h3>Реферальная система</h3>
      <p>+50 TRGR за каждого друга. Отслеживай приглашённых, смотри статистику в профиле.</p>
      <span class="feature-badge">+50 TRGR/friend</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">🔔</span>
      <h3>Умные напоминания</h3>
      <p>Дневник в 20:00, триггеры в 13:00, случайные чек-ины. 5 напоминаний в день без спама.</p>
      <span class="feature-badge">Scheduler</span>
    </div>
    
    <div class="feature-card">
      <span class="feature-icon">📱</span>
      <h3>Mini App</h3>
      <p>Полноценное веб-приложение в Telegram. 5 вкладок: профиль, триггеры, дневник, задачи, магазин.</p>
      <span class="feature-badge">Web interface</span>
    </div>
  </div>
  
  <!-- AI MODELS -->
  <div class="ai-features">
    <div class="ai-card">
      <div class="ai-icon">🤖</div>
      <h4>Claude (Anthropic)</h4>
      <p>Лучшее качество анализа</p>
    </div>
    <div class="ai-card">
      <div class="ai-icon">⚡</div>
      <h4>Groq Cloud</h4>
      <p>Мгновенные ответы</p>
    </div>
    <div class="ai-card">
      <div class="ai-icon">💎</div>
      <h4>Google Gemini</h4>
      <p>Мультимодальный AI</p>
    </div>
    <div class="ai-card">
      <div class="ai-icon">🎯</div>
      <h4>Vosk STT</h4>
      <p>Оффлайн-транскрибация</p>
    </div>
  </div>
</section>

<!-- HOW IT WORKS -->
<section style="border-top:1px solid var(--border)">
  <span class="section-tag">🎮 Процесс</span>
  <h2>Три шага к осознанности</h2>
  <p class="section-subtitle">Простой старт, глубокая трансформация</p>
  
  <div class="steps">
    <div class="step">
      <div class="step-num">1</div>
      <h3>Запусти бота</h3>
      <p>30-секундный онбординг. Подписка на канал = +50 стартовых TRGR. Первое касание с практикой.</p>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <h3>Практикуй ежедневно</h3>
      <p>Записывай триггеры, веди дневник, выполняй задачи. AI анализирует, scheduler напоминает.</p>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <h3>Получай результаты</h3>
      <p>Растут уровни, копятся TRGR, открываются достижения. Паттерны становятся видны.</p>
    </div>
  </div>
</section>

<!-- GAMIFICATION -->
<section style="border-top:1px solid var(--border)">
  <span class="section-tag">🎯 Геймификация</span>
  <h2>Твой прогресс в цифрах</h2>
  <p class="section-subtitle">Каждое действие приносит очки и приближает к новому уровню</p>
  
  <div class="gamification-grid">
    <div class="gam-card">
      <div class="gam-icon">📝</div>
      <div class="gam-value">+5</div>
      <div class="gam-label">За триггер</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">💭</div>
      <div class="gam-value">+2</div>
      <div class="gam-label">За эмоцию</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">💡</div>
      <div class="gam-value">+3</div>
      <div class="gam-label">За инсайт</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">📔</div>
      <div class="gam-value">+10</div>
      <div class="gam-label">За дневник</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">🔥</div>
      <div class="gam-value">+20</div>
      <div class="gam-label">Серия 7 дней</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">👥</div>
      <div class="gam-value">+50</div>
      <div class="gam-label">За друга</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">🧩</div>
      <div class="gam-value">+10</div>
      <div class="gam-label">Проработка</div>
    </div>
    <div class="gam-card">
      <div class="gam-icon">🛑</div>
      <div class="gam-value">+3</div>
      <div class="gam-label">Стоп-режим</div>
    </div>
  </div>
</section>

<!-- LEVELS -->
<section style="border-top:1px solid var(--border)">
  <span class="section-tag">📈 Уровни</span>
  <h2>5 уровней трансформации</h2>
  <p class="section-subtitle">От наблюдателя к автору своей реальности</p>
  
  <div class="levels">
    <div class="level-row">
      <div class="level-icon">👁</div>
      <div class="level-info">
        <div class="level-name">Наблюдатель</div>
        <div class="level-desc">Начало пути — ты начинаешь замечать себя</div>
      </div>
      <div class="level-xp">0 XP</div>
    </div>
    <div class="level-row">
      <div class="level-icon">🔍</div>
      <div class="level-info">
        <div class="level-name">Исследователь себя</div>
        <div class="level-desc">Ты изучаешь свои паттерны и реакции</div>
      </div>
      <div class="level-xp">100 XP</div>
    </div>
    <div class="level-row">
      <div class="level-icon">🧘</div>
      <div class="level-info">
        <div class="level-name">Практик осознанности</div>
        <div class="level-desc">Практики стали ежедневной привычкой</div>
      </div>
      <div class="level-xp">300 XP</div>
    </div>
    <div class="level-row">
      <div class="level-icon">🎮</div>
      <div class="level-info">
        <div class="level-name">Игрок своей жизни</div>
        <div class="level-desc">Ты управляешь реакциями, а не они тобой</div>
      </div>
      <div class="level-xp">700 XP</div>
    </div>
    <div class="level-row">
      <div class="level-icon">✨</div>
      <div class="level-info">
        <div class="level-name">Автор своей реальности</div>
        <div class="level-desc">Ты создаёшь жизнь осознанно и намеренно</div>
      </div>
      <div class="level-xp">1500 XP</div>
    </div>
  </div>
</section>

<!-- TESTIMONIAL -->
<section style="border-top:1px solid var(--border)">
  <div class="testimonial">
    <p class="testimonial-text">«За 30 дней я заметил больше паттернов, чем за 3 года терапии. AI-анализ паттернов — это просто вау. Видеть свои глубинные убеждения чёрным по белому...»</p>
    <p class="testimonial-author">— пользователь MindGame</p>
  </div>
</section>

<!-- ADMIN LOGIN -->
<section id="admin-login" style="border-top:1px solid var(--border)">
  <span class="section-tag">🔐 Админ</span>
  <h2>Панель управления</h2>
  <div class="login-section">
    <form method="post" action="/login">
      <div class="field">
        <label>Логин</label>
        <input type="text" name="username" placeholder="admin" required autocomplete="username">
      </div>
      <div class="field">
        <label>Пароль</label>
        <input type="password" name="password" placeholder="••••••••" required autocomplete="current-password">
      </div>
      <button type="submit" class="login-btn">Войти →</button>
    </form>
  </div>
</section>

<footer>
  <p>MindGame Bot — <strong>@Vadimbagautdinov_bot</strong></p>
  <p style="margin-top:8px">Создан с ❤️ и AI для тех, кто хочет меняться</p>
  <p style="margin-top:16px;font-size:12px;color:var(--text-muted)">
    Powered by Claude, Groq, Gemini, HuggingFace, Vosk
  </p>
</footer>
</body>
</html>"""


# ─── Auth routes ──────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if request.session.get("authenticated"):
        return RedirectResponse("/admin", status_code=302)
    error_html = f'<div class="error-msg">❌ {error}</div>' if error else ""
    # Reuse the login form from the landing page as a standalone page
    return HTMLResponse(LOGIN_PAGE_HTML.replace("<!-- ERROR -->", error_html))


LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Вход — Admin Panel</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0D0D1A;color:#E2E8F0;display:flex;align-items:center;
         justify-content:center;min-height:100vh}
    .box{background:#13132A;border:1px solid #1E1E3A;border-radius:24px;
         padding:48px 40px;width:100%;max-width:400px}
    .logo{text-align:center;font-size:22px;font-weight:800;color:white;margin-bottom:32px}
    .logo span{color:#A78BFA}
    .field{margin-bottom:20px}
    label{display:block;font-size:13px;font-weight:600;color:#94A3B8;
          margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
    input{width:100%;padding:14px 16px;background:#0D0D1A;color:white;
          border:1.5px solid #1E1E3A;border-radius:12px;font-size:15px;outline:none}
    input:focus{border-color:#7C3AED}
    button{width:100%;padding:15px;background:linear-gradient(135deg,#7C3AED,#5B21B6);
           color:white;border:none;border-radius:12px;font-size:16px;font-weight:700;
           cursor:pointer;margin-top:8px}
    button:hover{opacity:.9}
    .back{text-align:center;margin-top:20px;font-size:14px;color:#94A3B8}
    .back a{color:#A78BFA}
    .error-msg{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);
               color:#FCA5A5;padding:12px 16px;border-radius:10px;
               font-size:14px;margin-bottom:20px;text-align:center}
  </style>
</head>
<body>
<div class="box">
  <div class="logo">Mind<span>Game</span> Admin</div>
  <!-- ERROR -->
  <form method="post" action="/login">
    <div class="field">
      <label>Логин</label>
      <input type="text" name="username" placeholder="admin" required autocomplete="username">
    </div>
    <div class="field">
      <label>Пароль</label>
      <input type="password" name="password" placeholder="••••••••" required autocomplete="current-password">
    </div>
    <button type="submit">Войти →</button>
  </form>
  <div class="back"><a href="/">← На главную</a></div>
</div>
</body>
</html>"""


@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/login?error=Неверный+логин+или+пароль", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Users stats
    total_users = await db_fetchone("SELECT COUNT(*) as c FROM users")
    active_today = await db_fetchone("SELECT COUNT(*) as c FROM users WHERE date(updated_at)=date('now')")
    subscribed = await db_fetchone("SELECT COUNT(*) as c FROM users WHERE is_subscribed=1")
    
    # Triggers stats
    triggers_today = await db_fetchone("SELECT COUNT(*) as c FROM triggers WHERE date(created_at)=date('now')")
    triggers_week = await db_fetchone("SELECT COUNT(*) as c FROM triggers WHERE date(created_at)>=date('now','-7 days')")
    triggers_total = await db_fetchone("SELECT COUNT(*) as c FROM triggers")
    triggers_with_emotion = await db_fetchone("SELECT COUNT(*) as c FROM triggers WHERE emotion_code IS NOT NULL")
    triggers_with_intensity = await db_fetchone("SELECT COUNT(*) as c FROM triggers WHERE intensity IS NOT NULL")
    
    # Diary stats
    diary_today = await db_fetchone("SELECT COUNT(*) as c FROM diary_entries WHERE date(created_at)=date('now')")
    diary_week = await db_fetchone("SELECT COUNT(*) as c FROM diary_entries WHERE date(created_at)>=date('now','-7 days')")
    diary_total = await db_fetchone("SELECT COUNT(*) as c FROM diary_entries")
    
    # Tasks stats
    tasks_total = await db_fetchone("SELECT COUNT(*) as c FROM tasks")
    tasks_new = await db_fetchone("SELECT COUNT(*) as c FROM tasks WHERE status='new'")
    tasks_done = await db_fetchone("SELECT COUNT(*) as c FROM tasks WHERE status='done'")
    
    # Achievements stats
    achievements_total = await db_fetchone("SELECT COUNT(*) as c FROM user_achievements")
    
    # Referrals stats
    referrals_total = await db_fetchone("SELECT COUNT(*) as c FROM users WHERE referred_by_user_id IS NOT NULL")
    
    # Points stats
    points_total = await db_fetchone("SELECT COALESCE(SUM(points_balance),0) as c FROM users")
    points_awarded = await db_fetchone("SELECT COALESCE(SUM(points_delta),0) as c FROM rewards_log")
    
    # Message templates stats
    messages_total = await db_fetchone("SELECT COUNT(*) as c FROM message_templates")
    messages_active = await db_fetchone("SELECT COUNT(*) as c FROM message_templates WHERE is_active=1")

    # Recent data
    recent_users = await db_fetchall("""
        SELECT telegram_id, first_name, username, points_balance, xp_balance, streak_days, created_at
        FROM users ORDER BY created_at DESC LIMIT 5
    """)

    recent_triggers = await db_fetchall("""
        SELECT t.id, t.raw_text, t.emotion_code, t.intensity, t.points_awarded, t.created_at,
               u.first_name, u.telegram_id
        FROM triggers t JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC LIMIT 5
    """)
    
    recent_diary = await db_fetchall("""
        SELECT d.id, d.body, d.mood_code, d.points_awarded, d.created_at,
               u.first_name, u.telegram_id
        FROM diary_entries d JOIN users u ON d.user_id = u.id
        ORDER BY d.created_at DESC LIMIT 5
    """)
    
    recent_tasks = await db_fetchall("""
        SELECT t.id, t.title, t.status, t.estimated_points, t.created_at,
               u.first_name, u.telegram_id
        FROM tasks t JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC LIMIT 5
    """)

    # Top emotions
    top_emotions = await db_fetchall("""
        SELECT emotion_code, COUNT(*) as cnt FROM triggers
        WHERE emotion_code IS NOT NULL
        GROUP BY emotion_code ORDER BY cnt DESC LIMIT 5
    """)
    
    emotion_labels = {
        'anger': '😤 Злость',
        'sadness': '😔 Грусть',
        'fear': '😨 Страх',
        'shame': '😳 Стыд',
        'anxiety': '😟 Тревога',
        'resentment': '😞 Обида',
        'irritation': '😤 Раздражение',
        'numbness': '😶 Онемение',
        'other': '💭 Другое'
    }

    stats_html = f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:20px">
      <div class="stat"><div class="stat-value">{total_users['c']}</div><div class="stat-label">Пользователей</div></div>
      <div class="stat"><div class="stat-value">{active_today['c']}</div><div class="stat-label">Активных сегодня</div></div>
      <div class="stat"><div class="stat-value">{subscribed['c']}</div><div class="stat-label">Подписано</div></div>
      <div class="stat"><div class="stat-value">{referrals_total['c']}</div><div class="stat-label">Рефералов</div></div>
      <div class="stat"><div class="stat-value">{triggers_total['c']}</div><div class="stat-label">Триггеров всего</div></div>
      <div class="stat"><div class="stat-value">{triggers_today['c']}</div><div class="stat-label">Триггеров сегодня</div></div>
      <div class="stat"><div class="stat-value">{triggers_week['c']}</div><div class="stat-label">Триггеров за неделю</div></div>
      <div class="stat"><div class="stat-value">{diary_total['c']}</div><div class="stat-label">Записей дневника</div></div>
      <div class="stat"><div class="stat-value">{tasks_total['c']}</div><div class="stat-label">Задач всего</div></div>
      <div class="stat"><div class="stat-value">{tasks_new['c']}</div><div class="stat-label">Новых задач</div></div>
      <div class="stat"><div class="stat-value">{tasks_done['c']}</div><div class="stat-label">Выполнено</div></div>
      <div class="stat"><div class="stat-value">{achievements_total['c']}</div><div class="stat-label">Достижений</div></div>
      <div class="stat"><div class="stat-value">{points_total['c']}</div><div class="stat-label">TRGR у пользователей</div></div>
      <div class="stat"><div class="stat-value">{points_awarded['c']}</div><div class="stat-label">TRGR начислено</div></div>
      <div class="stat"><div class="stat-value">{messages_active['c']}</div><div class="stat-label">Шаблонов сообщений</div></div>
    </div>"""

    users_rows = "".join(f"""
    <tr>
      <td><a href="/users/{u['telegram_id']}">{u['first_name'] or '—'}</a> {'@' + u['username'] if u.get('username') else ''}</td>
      <td>{level_badge(u.get('xp_balance', 0))}</td>
      <td><b>{u.get('points_balance', 0)}</b></td>
      <td>🔥 {u.get('streak_days', 0)} дн.</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(u['created_at'], short=True)}</td>
    </tr>""" for u in recent_users)

    trigger_rows = "".join(f"""
    <tr>
      <td class="trigger-text" title="{t['raw_text']}">{t['raw_text'][:50]}...</td>
      <td><a href="/users/{t['telegram_id']}">{t['first_name']}</a></td>
      <td>{t.get('emotion_code') or '—'}</td>
      <td>{t.get('intensity') or '—'}</td>
      <td>+{t.get('points_awarded', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(t['created_at'])}</td>
    </tr>""" for t in recent_triggers)
    
    diary_rows = "".join(f"""
    <tr>
      <td class="trigger-text" title="{d['body']}">{d['body'][:50]}...</td>
      <td><a href="/users/{d['telegram_id']}">{d['first_name']}</a></td>
      <td>{d.get('mood_code') or '—'}</td>
      <td>+{d.get('points_awarded', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(d['created_at'])}</td>
    </tr>""" for d in recent_diary)
    
    task_rows = "".join(f"""
    <tr>
      <td class="trigger-text" title="{t['title']}">{t['title'][:50]}...</td>
      <td><a href="/users/{t['telegram_id']}">{t['first_name']}</a></td>
      <td>{'✅' if t['status']=='done' else '⏳' if t['status']=='in_progress' else '🆕'}</td>
      <td>+{t.get('estimated_points', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(t['created_at'])}</td>
    </tr>""" for t in recent_tasks)
    
    emotion_rows = "".join(f"""
    <tr>
      <td>{emotion_labels.get(e['emotion_code'], e['emotion_code'])}</td>
      <td><b>{e['cnt']}</b></td>
      <td><div class="progress-bar" style="width:150px"><div class="progress-fill" style="width:{min(100, e['cnt']*5)}%"></div></div></td>
    </tr>""" for e in top_emotions)

    content = f"""
    {stats_html}
    
    <!-- Top Emotions -->
    <div class="card" style="margin-bottom:20px">
      <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">🎭 Топ эмоций</h3>
      <table><thead><tr><th>Эмоция</th><th>Количество</th><th>Прогресс</th></tr></thead>
      <tbody>{emotion_rows}</tbody></table>
    </div>
    
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:20px">
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">👥 Новые пользователи</h3>
        <table><thead><tr><th>Имя</th><th>Уровень</th><th>TRGR</th><th>Серия</th><th>Дата</th></tr></thead>
        <tbody>{users_rows}</tbody></table>
        <div style="margin-top:12px"><a href="/users">Все пользователи →</a></div>
      </div>
      
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">📝 Последние триггеры</h3>
        <table><thead><tr><th>Триггер</th><th>Пользователь</th><th>Эмоция</th><th>Инт.</th><th>Очки</th><th>Время</th></tr></thead>
        <tbody>{trigger_rows}</tbody></table>
        <div style="margin-top:12px"><a href="/triggers">Все триггеры →</a></div>
      </div>
      
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">📔 Последние записи дневника</h3>
        <table><thead><tr><th>Запись</th><th>Пользователь</th><th>Настроение</th><th>Очки</th><th>Время</th></tr></thead>
        <tbody>{diary_rows}</tbody></table>
        <div style="margin-top:12px"><a href="/diary">Все записи →</a></div>
      </div>
      
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">✅ Последние задачи</h3>
        <table><thead><tr><th>Задача</th><th>Пользователь</th><th>Статус</th><th>Очки</th><th>Время</th></tr></thead>
        <tbody>{task_rows}</tbody></table>
        <div style="margin-top:12px"><a href="/tasks">Все задачи →</a></div>
      </div>
      
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">🏆 Последние достижения</h3>
        <table><thead><tr><th>Достижение</th><th>Пользователь</th><th>Дата</th></tr></thead>
        <tbody>{"".join(f"""
        <tr>
          <td>🏆 {a.get('title', '—')}</td>
          <td><a href="/users/{a['telegram_id']}">{a['first_name']}</a></td>
          <td style="color:#9CA3AF;font-size:12px">{fmt_date(a['awarded_at'], short=True)}</td>
        </tr>""" for a in await db_fetchall("""
            SELECT ua.awarded_at, a.title, a.icon, u.first_name, u.telegram_id
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_id = a.id
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.awarded_at DESC LIMIT 5
        """))}</tbody></table>
        <div style="margin-top:12px"><a href="/achievements">Все достижения →</a></div>
      </div>
      
      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">👥 Топ рефералов</h3>
        <table><thead><tr><th>Имя</th><th>Код</th><th>Приведено</th></tr></thead>
        <tbody>{"".join(f"""
        <tr>
          <td><a href="/users/{r['telegram_id']}">{r['first_name']}</a></td>
          <td style="font-family:monospace;font-size:12px">{r['referral_code']}</td>
          <td><b>{r['referrals_count']}</b></td>
        </tr>""" for r in await db_fetchall("""
            SELECT u.first_name, u.telegram_id, u.referral_code,
                   (SELECT COUNT(*) FROM users r WHERE r.referred_by_user_id = u.id) as referrals_count
            FROM users u
            WHERE referrals_count > 0
            ORDER BY referrals_count DESC LIMIT 5
        """))}</tbody></table>
        <div style="margin-top:12px"><a href="/referrals">Все рефералы →</a></div>
      </div>
    </div>"""

    return page("📊 Дашборд", content, "dashboard")


# ─── Users ────────────────────────────────────────────────────────────────────

@app.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, search: str = ""):
    if search:
        users = await db_fetchall("""
            SELECT u.*, COUNT(t.id) as trigger_count
            FROM users u LEFT JOIN triggers t ON t.user_id = u.id
            WHERE u.first_name LIKE ? OR u.username LIKE ? OR CAST(u.telegram_id AS TEXT) LIKE ?
            GROUP BY u.id ORDER BY u.created_at DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        users = await db_fetchall("""
            SELECT u.*, COUNT(t.id) as trigger_count
            FROM users u LEFT JOIN triggers t ON t.user_id = u.id
            GROUP BY u.id ORDER BY u.created_at DESC LIMIT 100
        """)

    rows = "".join(f"""
    <tr>
      <td><a href="/users/{u['telegram_id']}"><b>{u.get('first_name') or '—'}</b></a>
          {'<br><span style="color:#9CA3AF;font-size:12px">@' + u['username'] + '</span>' if u.get('username') else ''}</td>
      <td style="color:#6B7280;font-size:12px">{u['telegram_id']}</td>
      <td>{level_badge(u.get('xp_balance', 0))}</td>
      <td><b>{u.get('points_balance', 0)}</b></td>
      <td>{u.get('xp_balance', 0)}</td>
      <td>{u.get('trigger_count', 0)}</td>
      <td>🔥 {u.get('streak_days', 0)}</td>
      <td>{'✅' if u.get('is_subscribed') else '❌'}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(u['created_at'], short=True)}</td>
    </tr>""" for u in users)

    content = f"""
    <div class="card">
      <form method="get" style="display:flex;gap:8px;margin-bottom:16px">
        <input name="search" value="{search}" placeholder="Поиск по имени, username, ID..." style="width:300px">
        <button type="submit" class="btn btn-blue">Найти</button>
        {'<a href="/users" class="btn btn-gray" style="background:#F3F4F6;color:#374151">Сбросить</a>' if search else ''}
      </form>
      <table>
        <thead><tr>
          <th>Имя</th><th>Telegram ID</th><th>Уровень</th>
          <th>TRGR</th><th>XP</th><th>Триггеры</th><th>Серия</th><th>Подписка</th><th>Дата</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return page("👥 Пользователи", content, "users")


@app.get("/users/{telegram_id}", response_class=HTMLResponse)
async def user_detail(request: Request, telegram_id: int):
    user = await db_fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    if not user:
        raise HTTPException(404, "User not found")

    triggers = await db_fetchall("""
        SELECT * FROM triggers WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
    """, (user["id"],))

    diary = await db_fetchall("""
        SELECT * FROM diary_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT 5
    """, (user["id"],))

    rewards = await db_fetchall("""
        SELECT * FROM rewards_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
    """, (user["id"],))

    achievements = await db_fetchall("""
        SELECT a.title, a.icon, ua.awarded_at FROM achievements a
        JOIN user_achievements ua ON a.id = ua.achievement_id
        WHERE ua.user_id = ?
    """, (user["id"],))

    level_num, level_name = get_level(user.get("xp_balance", 0))

    ach_html = "".join(f'<span class="tag">{a["icon"]} {a["title"]}</span>' for a in achievements) or '<span style="color:#9CA3AF">Пока нет достижений</span>'

    trigger_rows = "".join(f"""
    <tr>
      <td style="font-size:13px">{t['raw_text'][:80]}</td>
      <td>{t.get('emotion_code') or '—'}</td>
      <td>{t.get('intensity') or '—'}</td>
      <td>{t.get('category_code') or '—'}</td>
      <td>+{t.get('points_awarded', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(t['created_at'])}</td>
    </tr>""" for t in triggers)

    reward_rows = "".join(f"""
    <tr>
      <td style="font-size:13px">{r['description'] or r['event_type']}</td>
      <td style="color:{'#10B981' if r['points_delta'] >= 0 else '#EF4444'}">
        {'+'if r['points_delta'] >= 0 else ''}{r['points_delta']}
      </td>
      <td><b>{r['balance_after']}</b></td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(r['created_at'])}</td>
    </tr>""" for r in rewards)

    content = f"""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
      <a href="/users" style="color:#6B7280;font-size:14px">← Все пользователи</a>
    </div>

    <div style="display:grid;grid-template-columns:300px 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <div style="font-size:40px;text-align:center;margin-bottom:12px">👤</div>
        <h3 style="text-align:center;font-size:18px">{user.get('first_name','')} {user.get('last_name','')}</h3>
        <p style="text-align:center;color:#6B7280;margin-bottom:16px">{'@' + user['username'] if user.get('username') else ''}</p>
        <div style="font-size:13px;display:flex;flex-direction:column;gap:8px">
          <div>🆔 {user['telegram_id']}</div>
          <div>{level_badge(user.get('xp_balance', 0))}</div>
          <div>💰 <b>{user.get('points_balance', 0)}</b> TRGR</div>
          <div>⚡ {user.get('xp_balance', 0)} XP</div>
          <div>🔥 Серия: {user.get('streak_days', 0)} дн.</div>
          <div>📝 Триггеров: {len(triggers)}</div>
          <div>{'✅ Подписан' if user.get('is_subscribed') else '❌ Не подписан'}</div>
          <div style="color:#9CA3AF">С {fmt_date(user['created_at'], short=True)}</div>
        </div>
        <div style="margin-top:16px;padding-top:16px;border-top:1px solid #F3F4F6">
          <p style="font-size:13px;font-weight:600;margin-bottom:8px">Скорректировать TRGR:</p>
          <form method="post" action="/users/{telegram_id}/adjust-points" style="display:flex;flex-direction:column;gap:8px">
            <input type="number" name="delta" placeholder="+100 или -50" style="width:100%">
            <input type="text" name="reason" placeholder="Причина" style="width:100%">
            <button type="submit" class="btn btn-blue" style="width:100%">Применить</button>
          </form>
        </div>
      </div>

      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <h3 style="font-size:15px;font-weight:700;margin-bottom:8px">🏆 Достижения</h3>
          {ach_html}
        </div>
        <div class="card">
          <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">💰 История начислений</h3>
          <table><thead><tr><th>Действие</th><th>Изменение</th><th>Баланс</th><th>Время</th></tr></thead>
          <tbody>{reward_rows}</tbody></table>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="font-size:15px;font-weight:700;margin-bottom:12px">📝 Триггеры пользователя</h3>
      <table><thead><tr><th>Текст</th><th>Эмоция</th><th>Инт.</th><th>Категория</th><th>Очки</th><th>Время</th></tr></thead>
      <tbody>{trigger_rows}</tbody></table>
    </div>"""

    return page(f"👤 {user.get('first_name', 'Пользователь')}", content, "users")


@app.post("/users/{telegram_id}/adjust-points")
async def adjust_points(telegram_id: int, delta: int = Form(...), reason: str = Form("")):
    user = await db_fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    if not user:
        raise HTTPException(404)

    new_balance = max(0, user["points_balance"] + delta)
    new_xp = max(0, user["xp_balance"] + delta)
    await db_execute("""
        UPDATE users SET points_balance = ?, xp_balance = ?, updated_at = datetime('now')
        WHERE telegram_id = ?
    """, (new_balance, new_xp, telegram_id))

    await db_execute("""
        INSERT INTO rewards_log (user_id, event_type, points_delta, xp_delta, balance_after, description)
        VALUES (?, 'admin_adjustment', ?, ?, ?, ?)
    """, (user["id"], delta, delta, new_balance, f"Ручная корректировка: {reason or 'без причины'}"))

    return RedirectResponse(f"/users/{telegram_id}", status_code=303)


# ─── Triggers ─────────────────────────────────────────────────────────────────

@app.get("/triggers", response_class=HTMLResponse)
async def triggers_list(request: Request, emotion: str = "", category: str = ""):
    where = "1=1"
    params = []
    if emotion:
        where += " AND t.emotion_code = ?"
        params.append(emotion)
    if category:
        where += " AND t.category_code = ?"
        params.append(category)

    triggers = await db_fetchall(f"""
        SELECT t.*, u.first_name, u.username, u.telegram_id
        FROM triggers t JOIN users u ON t.user_id = u.id
        WHERE {where}
        ORDER BY t.created_at DESC LIMIT 100
    """, params)

    emotions = await db_fetchall("SELECT DISTINCT emotion_code FROM triggers WHERE emotion_code IS NOT NULL")
    categories = await db_fetchall("SELECT DISTINCT category_code FROM triggers WHERE category_code IS NOT NULL")

    emotion_opts = "".join(f'<option value="{e["emotion_code"]}" {"selected" if emotion == e["emotion_code"] else ""}>{e["emotion_code"]}</option>' for e in emotions)
    cat_opts = "".join(f'<option value="{c["category_code"]}" {"selected" if category == c["category_code"] else ""}>{c["category_code"]}</option>' for c in categories)

    rows = "".join(f"""
    <tr>
      <td style="font-size:13px;max-width:350px">{t['raw_text'][:120]}</td>
      <td><a href="/users/{t['telegram_id']}">{t.get('first_name') or '—'}</a></td>
      <td>{t.get('emotion_code') or '—'}</td>
      <td>{t.get('intensity') or '—'}</td>
      <td>{t.get('category_code') or '—'}</td>
      <td>{'✅' if t.get('insight_text') else '—'}</td>
      <td>+{t.get('points_awarded', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(t['created_at'])}</td>
      <td>
        <a href="/triggers/delete/{t['id']}" class="btn btn-red" style="padding:4px 8px;font-size:11px" onclick="return confirm('Удалить триггер #{t['id']}?')">🗑</a>
      </td>
    </tr>""" for t in triggers)

    # Сообщение об успешном удалении
    deleted_msg = ""
    if request.query_params.get("deleted") == "1":
        deleted_msg = '<div style="background:#D1FAE5;border:1px solid #10B981;color:#065F46;padding:12px;border-radius:8px;margin-bottom:16px;text-align:center">✅ Триггер удалён</div>'

    content = f"""
    <div class="card">
      {deleted_msg}
      <form method="get" style="display:flex;gap:8px;margin-bottom:16px;align-items:center">
        <label style="font-size:13px;color:#6B7280">Эмоция:</label>
        <select name="emotion"><option value="">Все</option>{emotion_opts}</select>
        <label style="font-size:13px;color:#6B7280">Категория:</label>
        <select name="category"><option value="">Все</option>{cat_opts}</select>
        <button type="submit" class="btn btn-blue">Фильтр</button>
        <a href="/triggers" style="font-size:13px;color:#6B7280">Сбросить</a>
      </form>
      <table>
        <thead><tr>
          <th>Триггер</th><th>Пользователь</th><th>Эмоция</th>
          <th>Инт.</th><th>Категория</th><th>Вывод</th><th>Очки</th><th>Время</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return page("📝 Триггеры", content, "triggers")


# ─── Diary ────────────────────────────────────────────────────────────────────

@app.get("/diary", response_class=HTMLResponse)
async def diary_list(request: Request):
    entries = await db_fetchall("""
        SELECT d.*, u.first_name, u.telegram_id
        FROM diary_entries d JOIN users u ON d.user_id = u.id
        ORDER BY d.created_at DESC LIMIT 50
    """)

    rows = "".join(f"""
    <tr>
      <td style="font-size:13px;max-width:350px">{e['body'][:100]}{'...' if len(e.get('body','')) > 100 else ''}</td>
      <td><a href="/users/{e['telegram_id']}">{e.get('first_name') or '—'}</a></td>
      <td>{e.get('mood_code') or '—'}</td>
      <td>{e.get('energy_level') or '—'}</td>
      <td style="font-size:12px;color:#6B7280;max-width:200px">{e.get('insight_text') or '—'}</td>
      <td>+{e.get('points_awarded', 0)}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(e['created_at'])}</td>
    </tr>""" for e in entries)

    content = f"""
    <div class="card">
      <table>
        <thead><tr>
          <th>Запись</th><th>Пользователь</th><th>Настроение</th>
          <th>Энергия</th><th>Инсайт</th><th>Очки</th><th>Время</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return page("📔 Дневник", content, "diary")


# ─── Achievements ─────────────────────────────────────────────────────────────

@app.get("/achievements", response_class=HTMLResponse)
async def achievements_list(request: Request):
    achievements = await db_fetchall("""
        SELECT a.*, COUNT(ua.id) as awarded_count
        FROM achievements a LEFT JOIN user_achievements ua ON a.id = ua.achievement_id
        GROUP BY a.id ORDER BY awarded_count DESC
    """)

    rows = "".join(f"""
    <tr>
      <td>{a['icon']} <b>{a['title']}</b></td>
      <td style="color:#6B7280;font-size:13px">{a.get('description') or '—'}</td>
      <td><code style="background:#F3F4F6;padding:2px 6px;border-radius:4px">{a['code']}</code></td>
      <td>{a.get('rule_type') or '—'} {a.get('rule_value') or ''}</td>
      <td><b>{a['awarded_count']}</b> чел.</td>
      <td>{'<span class="badge badge-green">Активно</span>' if a.get('is_active') else '<span class="badge badge-gray">Выкл</span>'}</td>
    </tr>""" for a in achievements)

    content = f"""
    <div class="card">
      <table>
        <thead><tr>
          <th>Достижение</th><th>Описание</th><th>Код</th><th>Правило</th><th>Выдано</th><th>Статус</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return page("🏆 Достижения", content, "achievements")


# ─── Broadcasts ───────────────────────────────────────────────────────────────

ROLES = {
    "all":          ("Все пользователи",              "SELECT telegram_id FROM users"),
    "subscribed":   ("Подписанные на канал",           "SELECT telegram_id FROM users WHERE is_subscribed = 1"),
    "active_week":  ("Активные за последние 7 дней",  "SELECT telegram_id FROM users WHERE updated_at >= datetime('now','-7 days')"),
    "inactive":     ("Неактивные 7+ дней",             "SELECT telegram_id FROM users WHERE updated_at < datetime('now','-7 days')"),
    "level_1":      ("Уровень 1 — Наблюдатель",       "SELECT telegram_id FROM users WHERE xp_balance < 100"),
    "level_2":      ("Уровень 2 — Исследователь",     "SELECT telegram_id FROM users WHERE xp_balance >= 100 AND xp_balance < 300"),
    "level_3":      ("Уровень 3 — Практик",           "SELECT telegram_id FROM users WHERE xp_balance >= 300 AND xp_balance < 700"),
    "level_4_5":    ("Уровень 4–5 — Продвинутые",     "SELECT telegram_id FROM users WHERE xp_balance >= 700"),
    "no_triggers":  ("Не записали ни одного триггера","SELECT u.telegram_id FROM users u LEFT JOIN triggers t ON t.user_id = u.id GROUP BY u.id HAVING COUNT(t.id) = 0"),
    "streak_7":     ("Серия 7+ дней подряд",          "SELECT telegram_id FROM users WHERE streak_days >= 7"),
}


async def count_role(role: str) -> int:
    query = ROLES.get(role, ("", "SELECT telegram_id FROM users WHERE 0"))[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"SELECT COUNT(*) FROM ({query})") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_role_ids(role: str) -> list[int]:
    query = ROLES.get(role, ("", "SELECT telegram_id FROM users WHERE 0"))[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def send_telegram_message(telegram_id: int, text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": telegram_id,
                "text": text,
                "parse_mode": "HTML"
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
    except Exception:
        return False


async def run_broadcast(broadcast_id: int, role: str, text: str):
    ids = await get_role_ids(role)
    sent = 0
    failed = 0
    for tg_id in ids:
        ok = await send_telegram_message(tg_id, text)
        if ok:
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 msg/sec — within Telegram limits

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE broadcasts SET sent_count=?, failed_count=?, status='done', finished_at=datetime('now')
            WHERE id=?
        """, (sent, failed, broadcast_id))
        await db.commit()


@app.get("/broadcasts", response_class=HTMLResponse)
async def broadcasts_page(request: Request):
    history = await db_fetchall("""
        SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT 30
    """)

    # Count for each role
    role_counts = {}
    for key in ROLES:
        role_counts[key] = await count_role(key)

    role_options = "".join(
        f'<option value="{key}">{label} ({role_counts.get(key, 0)} чел.)</option>'
        for key, (label, _) in ROLES.items()
    )

    history_rows = "".join(f"""
    <tr>
      <td style="font-size:13px;max-width:300px;white-space:pre-line">{h['message_text'][:120]}{'...' if len(h['message_text']) > 120 else ''}</td>
      <td>{ROLES.get(h['target_role'], (h['target_role'], ''))[0]}</td>
      <td>
        {'<span class="badge badge-green">Отправлено</span>' if h['status'] == 'done' else
         '<span class="badge" style="background:#FEF3C7;color:#92400E">В процессе</span>'}
      </td>
      <td style="color:#10B981"><b>✅ {h['sent_count']}</b></td>
      <td style="color:#EF4444">{('❌ ' + str(h['failed_count'])) if h['failed_count'] else '—'}</td>
      <td style="color:#9CA3AF;font-size:12px">{fmt_date(h['created_at'])}</td>
    </tr>""" for h in history)

    content = f"""
    <div style="display:grid;grid-template-columns:420px 1fr;gap:20px">

      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:16px">✉️ Новая рассылка</h3>
        <form method="post" action="/broadcasts/send" id="bc-form">
          <div style="margin-bottom:12px">
            <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px">
              Кому отправить:
            </label>
            <select name="role" id="role-select" style="width:100%" onchange="updateCount(this)">
              {role_options}
            </select>
            <div id="role-count" style="font-size:12px;color:#6B7280;margin-top:4px"></div>
          </div>

          <div style="margin-bottom:12px">
            <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px">
              Текст сообщения:
            </label>
            <textarea name="message_text" rows="8" style="width:100%;padding:8px 12px;border:1px solid #D1D5DB;border-radius:8px;font-size:14px;font-family:inherit;resize:vertical"
              placeholder="Напишите сообщение... Поддерживается HTML: &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;, &lt;a href=&quot;...&quot;&gt;ссылка&lt;/a&gt;"></textarea>
          </div>

          <div style="background:#FEF3C7;border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px;color:#92400E">
            ⚠️ Сообщение будет отправлено всем выбранным пользователям. Действие необратимо.
          </div>

          <button type="submit" class="btn btn-blue" style="width:100%;padding:10px"
            onclick="return confirm('Отправить рассылку?')">
            📢 Отправить рассылку
          </button>
        </form>
      </div>

      <div class="card">
        <h3 style="font-size:15px;font-weight:700;margin-bottom:16px">📋 История рассылок</h3>
        {'<p style="color:#9CA3AF;font-size:14px">Рассылок ещё не было</p>' if not history else f'''
        <table>
          <thead><tr>
            <th>Сообщение</th><th>Аудитория</th><th>Статус</th><th>Отправлено</th><th>Ошибки</th><th>Время</th>
          </tr></thead>
          <tbody>{history_rows}</tbody>
        </table>'''}
      </div>

    </div>

    <script>
    const counts = {{}};
    document.querySelectorAll('#role-select option').forEach(opt => {{
        const match = opt.text.match(/\\((\\d+) чел\\.\\)/);
        if (match) counts[opt.value] = parseInt(match[1]);
    }});
    function updateCount(sel) {{
        const c = counts[sel.value] || 0;
        document.getElementById('role-count').textContent = `Получателей: ${{c}} чел.`;
    }}
    updateCount(document.getElementById('role-select'));
    </script>"""

    return page("📢 Рассылки", content, "broadcasts")


@app.post("/broadcasts/send")
async def send_broadcast(
    request: Request,
    role: str = Form(...),
    message_text: str = Form(...)
):
    if not message_text.strip():
        raise HTTPException(400, "Пустое сообщение")
    if role not in ROLES:
        raise HTTPException(400, "Неизвестная роль")

    # Save broadcast record
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO broadcasts (target_role, message_text, status)
            VALUES (?, ?, 'sending')
        """, (role, message_text.strip()))
        broadcast_id = cursor.lastrowid
        await db.commit()

    # Run broadcast in background
    asyncio.create_task(run_broadcast(broadcast_id, role, message_text.strip()))

    return RedirectResponse("/broadcasts?sent=1", status_code=303)


# ─── Points Configuration ──────────────────────────────────────────────────────

@app.get("/points", response_class=HTMLResponse)
async def points_page(request: Request):
    rules = await db_fetchall("SELECT id, rule_name, points_value, category, description FROM points_config ORDER BY category, rule_name")

    # Group by category
    by_category = {}
    for rule in rules:
        cat = rule["category"] or "other"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(rule)

    # Build table HTML
    table_html = ""
    cat_labels = {
        "triggers": "📝 Триггеры",
        "diary": "📔 Дневник",
        "events": "🎉 События",
        "other": "📋 Прочее"
    }

    for cat in ["triggers", "diary", "events", "other"]:
        if cat not in by_category:
            continue
        rules_in_cat = by_category[cat]
        table_html += f'<tr><td colspan="3" style="background:#1F2937;color:white;font-weight:700;padding:12px">{cat_labels.get(cat, cat)}</td></tr>'
        for r in rules_in_cat:
            table_html += f'''
            <tr>
                <td><code>{r["rule_name"]}</code></td>
                <td>{r["description"] or ""}</td>
                <td>
                    <form method="post" action="/points/update" style="display:flex;gap:8px;align-items:center">
                        <input type="hidden" name="rule_name" value="{r["rule_name"]}">
                        <input type="number" name="points_value" value="{r["points_value"]}" style="width:80px;padding:6px;border:1px solid #D1D5DB;border-radius:6px">
                        <button type="submit" class="btn btn-blue" style="padding:6px 12px;font-size:12px">Сохранить</button>
                    </form>
                </td>
            </tr>
            '''

    content = f'''
    <div class="card">
        <p style="margin-bottom:24px;color:#6B7280">
            Управление правилами начисления TRGR. Изменения вступают в силу сразу.
        </p>
        <table>
            <thead>
                <tr>
                    <th style="width:180px">Правило</th>
                    <th style="flex:1">Описание</th>
                    <th style="width:200px">TRGR</th>
                </tr>
            </thead>
            <tbody>{table_html}</tbody>
        </table>
    </div>
    '''

    return HTMLResponse(page("⭐ Конфигурация очков", content, "points"))


@app.post("/points/update")
async def update_points(request: Request, rule_name: str = Form(...), points_value: int = Form(...)):
    result = await db_execute(
        "UPDATE points_config SET points_value = ?, updated_at = datetime('now') WHERE rule_name = ?",
        (points_value, rule_name)
    )

    # Reload cache in config
    from config import load_points_from_db
    await load_points_from_db()

    return RedirectResponse("/points?updated=1", status_code=303)


# ─── Menu Settings ─────────────────────────────────────────────────────────────

MENU_LABELS = {
    "show_diary":         ("📔 Дневник",         "Кнопка для ежедневных записей"),
    "show_triggers_list": ("📋 Мои триггеры",    "Просмотр списка всех триггеров"),
    "show_tasks":         ("✅ Мои задачи",       "Управление задачами"),
    "show_progress":      ("📊 Мой прогресс",    "Статистика и достижения"),
    "show_checkin":       ("✅ Быстрый чек-ин",  "Быстрая проверка состояния"),
    "show_shop":          ("🛍 Магазин",          "Магазин для трат TRGR"),
    "show_stop":          ("🛑 Стоп",             "Экстренная остановка триггера"),
    "show_settings":      ("⚙️ Настройки",        "Настройки уведомлений"),
}


@app.get("/menu", response_class=HTMLResponse)
async def menu_settings_page(request: Request):
    rows = await db_fetchall("SELECT key, value, label FROM menu_settings ORDER BY key")
    # If table doesn't exist yet (before migration), show empty
    if not rows:
        content = '<div class="card"><p style="color:#9CA3AF">Таблица menu_settings не найдена. Перезапусти бота для применения миграции.</p></div>'
        return HTMLResponse(page("🎛 Меню бота", content, "menu"))

    updated = request.query_params.get("updated")
    alert = '<div style="background:#D1FAE5;color:#065F46;padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px">✅ Настройки сохранены</div>' if updated else ""

    toggle_rows = ""
    for r in rows:
        key = r["key"]
        label_text, hint = MENU_LABELS.get(key, (r.get("label") or key, ""))
        is_on = bool(r["value"])
        toggle_rows += f"""
        <tr>
          <td style="font-size:15px;font-weight:600">{label_text}</td>
          <td style="color:#6B7280;font-size:13px">{hint}</td>
          <td>
            <form method="post" action="/menu/update" style="display:inline">
              <input type="hidden" name="key" value="{key}">
              <input type="hidden" name="value" value="{'0' if is_on else '1'}">
              <button type="submit" class="btn {'btn-green' if is_on else 'btn-red'}" style="min-width:90px">
                {'✅ Вкл' if is_on else '❌ Выкл'}
              </button>
            </form>
          </td>
        </tr>"""

    content = f"""
    {alert}
    <div class="card">
      <p style="margin-bottom:20px;color:#6B7280;font-size:14px">
        Управление видимостью кнопок в Reply-клавиатуре бота.<br>
        Кнопка <b>📝 Записать триггер</b> всегда отображается.
        Изменения вступают в силу немедленно.
      </p>
      <table>
        <thead>
          <tr>
            <th style="width:200px">Кнопка</th>
            <th>Описание</th>
            <th style="width:120px">Статус</th>
          </tr>
        </thead>
        <tbody>{toggle_rows}</tbody>
      </table>
    </div>"""

    return HTMLResponse(page("🎛 Меню бота", content, "menu"))


@app.post("/menu/update")
async def update_menu_setting(request: Request, key: str = Form(...), value: str = Form(...)):
    enabled = value == "1"
    await db_execute(
        "UPDATE menu_settings SET value = ?, updated_at = datetime('now') WHERE key = ?",
        (1 if enabled else 0, key)
    )
    # Reload cache so keyboard changes take effect immediately
    from config import load_menu_from_db
    await load_menu_from_db()
    return RedirectResponse("/menu?updated=1", status_code=303)


# ─── Message Templates ────────────────────────────────────────────────────────

@app.get("/messages", response_class=HTMLResponse)
async def messages_list(request: Request, category: str = "all"):
    if category and category != "all":
        templates = await db_fetchall("SELECT * FROM message_templates WHERE category = ? ORDER BY sort_order, template_name", (category,))
    else:
        templates = await db_fetchall("SELECT * FROM message_templates ORDER BY category, sort_order, template_name")
    
    categories = ["all", "general", "onboarding", "trigger", "diary", "task", "stop"]
    category_labels = {
        "all": "📋 Все",
        "general": "🏠 Общие",
        "onboarding": "🎮 Онбординг",
        "trigger": "📝 Триггеры",
        "diary": "📔 Дневник",
        "task": "✅ Задачи",
        "stop": "🛑 Стоп-режим"
    }
    
    cat_filter = "".join(f"""
        <a href="/messages?category={cat}" 
           style="padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none;
                  background:{'#3B82F6' if category == cat else '#F3F4F6'};
                  color:{'white' if category == cat else '#374151'}">
          {category_labels.get(cat, cat)}
        </a>
    """ for cat in categories)
    
    rows = "".join(f"""
    <tr>
      <td><b>{t['template_name']}</b><br><span style="color:#6B7280;font-size:12px">{t['template_key']}</span></td>
      <td><span style="background:#EEF2FF;color:#4338CA;padding:2px 8px;border-radius:6px;font-size:11px">{t['category']}</span></td>
      <td style="color:#6B7280;font-size:12px">{t['message_type']}</td>
      <td style="font-size:13px;max-width:400px">{t['message_text'][:80]}{'...' if len(t['message_text']) > 80 else ''}</td>
      <td>{'✅' if t['is_active'] else '❌'}</td>
      <td>
        <a href="/messages/edit/{t['template_key']}" class="btn btn-blue" style="padding:4px 10px;font-size:12px">✏️</a>
      </td>
    </tr>""" for t in templates)
    
    content = f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="font-size:15px;font-weight:700">Шаблоны сообщений</h3>
        <a href="/messages/add" class="btn btn-green" style="padding:8px 16px">➕ Добавить</a>
      </div>
      <div style="margin-bottom:16px;display:flex;gap:8px;flex-wrap:wrap">
        {cat_filter}
      </div>
      <p style="color:#6B7280;font-size:13px;margin-bottom:16px">
        Здесь можно редактировать сообщения, которые бот отправляет автоматически.
      </p>
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Категория</th>
            <th>Тип</th>
            <th>Текст</th>
            <th>Активно</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    
    return page("💬 Сообщения", content, "messages")


@app.get("/messages/add", response_class=HTMLResponse)
async def message_add(request: Request):
    content = f"""
    <div class="card">
      <h3 style="font-size:15px;font-weight:700;margin-bottom:16px">Добавить шаблон</h3>
      <form method="post" action="/messages/add">
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Ключ (латиница)</label>
          <input type="text" name="template_key" placeholder="welcome_message" style="width:100%;padding:10px" required>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Название</label>
          <input type="text" name="template_name" placeholder="Приветственное сообщение" style="width:100%;padding:10px" required>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Тип</label>
          <select name="message_type" style="width:100%;padding:10px">
            <option value="text">Текст</option>
            <option value="notification">Уведомление</option>
            <option value="reminder">Напоминание</option>
          </select>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Сообщение</label>
          <textarea name="message_text" rows="6" style="width:100%;padding:10px;font-family:monospace" placeholder="Текст сообщения..."></textarea>
        </div>
        <div style="display:flex;gap:10px">
          <button type="submit" class="btn btn-green">Сохранить</button>
          <a href="/messages" class="btn btn-gray" style="background:#F3F4F6;color:#374151">Отмена</a>
        </div>
      </form>
    </div>"""
    return page("Добавить сообщение", content, "messages")


@app.post("/messages/add")
async def message_add_post(request: Request, template_key: str = Form(...), template_name: str = Form(...),
                           message_type: str = Form(...), message_text: str = Form(...)):
    await db_execute("""
        INSERT INTO message_templates (template_key, template_name, message_text, message_type)
        VALUES (?, ?, ?, ?)
    """, (template_key, template_name, message_text, message_type))
    return RedirectResponse("/messages", status_code=303)


@app.get("/messages/edit/{template_key}", response_class=HTMLResponse)
async def message_edit(request: Request, template_key: str):
    template = await db_fetchone("SELECT * FROM message_templates WHERE template_key = ?", (template_key,))
    if not template:
        raise HTTPException(404, "Шаблон не найден")
    
    content = f"""
    <div class="card">
      <a href="/messages" style="color:#6B7280;font-size:14px;margin-bottom:16px;display:block">← Назад к списку</a>
      <h3 style="font-size:15px;font-weight:700;margin-bottom:16px">Редактировать: {template['template_name']}</h3>
      <form method="post" action="/messages/edit/{template_key}">
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Ключ</label>
          <input type="text" value="{template['template_key']}" disabled style="width:100%;padding:10px;background:#F3F4F6;color:#6B7280">
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Название</label>
          <input type="text" name="template_name" value="{template['template_name']}" style="width:100%;padding:10px" required>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Тип</label>
          <select name="message_type" style="width:100%;padding:10px">
            <option value="text" {'selected' if template['message_type'] == 'text' else ''}>Текст</option>
            <option value="notification" {'selected' if template['message_type'] == 'notification' else ''}>Уведомление</option>
            <option value="reminder" {'selected' if template['message_type'] == 'reminder' else ''}>Напоминание</option>
          </select>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">Сообщение</label>
          <textarea name="message_text" rows="8" style="width:100%;padding:10px;font-family:monospace">{template['message_text']}</textarea>
        </div>
        <div style="margin-bottom:16px">
          <label style="display:flex;align-items:center;gap:8px">
            <input type="checkbox" name="is_active" value="1" {'checked' if template['is_active'] else ''} style="width:18px;height:18px">
            <span style="font-size:13px">Активно</span>
          </label>
        </div>
        <div style="display:flex;gap:10px">
          <button type="submit" class="btn btn-blue">Сохранить</button>
          <a href="/messages" class="btn btn-gray" style="background:#F3F4F6;color:#374151">Отмена</a>
        </div>
      </form>
    </div>"""
    return page("Редактировать сообщение", content, "messages")


@app.post("/messages/edit/{template_key}")
async def message_edit_post(request: Request, template_key: str, template_name: str = Form(...),
                            message_type: str = Form(...), message_text: str = Form(...),
                            is_active: str = Form(None)):
    await db_execute("""
        UPDATE message_templates 
        SET template_name = ?, message_text = ?, message_type = ?, is_active = ?, updated_at = datetime('now')
        WHERE template_key = ?
    """, (template_name, message_text, message_type, 1 if is_active else 0, template_key))
    return RedirectResponse("/messages", status_code=303)


@app.post("/messages/delete/{template_key}")
async def message_delete(request: Request, template_key: str):
    await db_execute("DELETE FROM message_templates WHERE template_key = ?", (template_key,))
    return RedirectResponse("/messages", status_code=303)


# ─── Referrals ────────────────────────────────────────────────────────────────

@app.get("/referrals", response_class=HTMLResponse)
async def referrals_list(request: Request, user_id: str = ""):
    if user_id:
        # Show referrals for specific user
        user = await db_fetchone("SELECT * FROM users WHERE id = ?", (int(user_id),))
        referrals = await db.get_user_referrals(int(user_id))
        
        ref_rows = "".join(f"""
        <tr>
          <td>{r['first_name'] or '—'} {'@' + r['username'] if r.get('username') else ''}</td>
          <td style="color:#6B7280;font-size:12px">{r['telegram_id']}</td>
          <td style="color:#6B7280;font-size:12px">{fmt_date(r['registered_at'])}</td>
        </tr>""" for r in referrals)
        
        content = f"""
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
          <a href="/referrals" style="color:#6B7280;font-size:14px">← Назад к списку</a>
        </div>
        
        <div class="card">
          <h3 style="font-size:15px;font-weight:700;margin-bottom:16px">
            Рефералы пользователя: {user.get('first_name', '—')}
          </h3>
          <p style="color:#6B7280;font-size:13px;margin-bottom:16px">
            Всего приведено: <b>{len(referrals)}</b>
          </p>
          {f'''
          <table>
            <thead>
              <tr>
                <th>Имя</th>
                <th>Telegram ID</th>
                <th>Дата регистрации</th>
              </tr>
            </thead>
            <tbody>{ref_rows}</tbody>
          </table>
          ''' if referrals else '<p style="color:#6B7280">Пока нет рефералов</p>'}
        </div>"""
    else:
        # Show all users with referrals
        stats = await db.get_referrals_stats()
        
        rows = "".join(f"""
        <tr>
          <td><b>{s['first_name'] or '—'}</b> {'@' + s['username'] if s.get('username') else ''}</td>
          <td style="color:#6B7280;font-size:12px">{s['telegram_id']}</td>
          <td style="font-family:monospace;background:#F3F4F6;padding:4px 8px;border-radius:4px">{s['referral_code']}</td>
          <td><b style="color:{'#10B981' if s['referrals_count'] > 0 else '#6B7280'}">{s['referrals_count']}</b></td>
          <td>{s['points_balance']}</td>
          <td style="color:#6B7280;font-size:12px">{fmt_date(s['created_at'], short=True)}</td>
          <td>
            <a href="/referrals?user_id={s['id']}" class="btn btn-blue" style="padding:4px 10px;font-size:12px">👥 Смотреть</a>
          </td>
        </tr>""" for s in stats)
        
        total_referrals = sum(s['referrals_count'] for s in stats)
        active_referrers = sum(1 for s in stats if s['referrals_count'] > 0)
        
        content = f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <h3 style="font-size:15px;font-weight:700">Рефералы</h3>
          </div>
          
          <div class="stats" style="margin-bottom:24px">
            <div class="stat">
              <div class="stat-v">{len(stats)}</div>
              <div class="stat-l">Участников</div>
            </div>
            <div class="stat">
              <div class="stat-v">{total_referrals}</div>
              <div class="stat-l">Всего рефералов</div>
            </div>
            <div class="stat">
              <div class="stat-v">{active_referrers}</div>
              <div class="stat-l">Привели друзей</div>
            </div>
          </div>
          
          <p style="color:#6B7280;font-size:13px;margin-bottom:16px">
            Пользователи у которых есть реферальный код
          </p>
          <table>
            <thead>
              <tr>
                <th>Имя</th>
                <th>Telegram ID</th>
                <th>Реферальный код</th>
                <th>Приведено</th>
                <th>Баланс</th>
                <th>Дата</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""
    
    return page("👥 Рефералы", content, "referrals")


# ─── Support Messages ─────────────────────────────────────────────────────────

@app.get("/support", response_class=HTMLResponse)
async def support_messages(
    request: Request,
    status: str = "",
    page_num: int = 1
):
    """Страница сообщений поддержки."""
    limit = 50
    
    # Получаем сообщения
    messages = await db.get_support_messages_for_admin(status=status if status else None, limit=limit)
    
    # Статистика
    stats = await db.get_support_stats()
    
    # Формируем контент
    stats_html = f"""
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{stats.get('total', 0)}</div>
            <div class="stat-label">Всего</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color:#3B82F6">{stats.get('new_count', 0)}</div>
            <div class="stat-label">🆕 Новые</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color:#F59E0B">{stats.get('in_progress_count', 0)}</div>
            <div class="stat-label">⏳ В работе</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color:#10B981">{stats.get('resolved_count', 0)}</div>
            <div class="stat-label">✅ Решено</div>
        </div>
    </div>
    """
    
    # Фильтры
    filters_html = """
    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
        <a href="/support" class="btn btn-blue">Все</a>
        <a href="/support?status=new" class="btn btn-green">🆕 Новые</a>
        <a href="/support?status=in_progress" class="btn" style="background:#F59E0B;color:white">⏳ В работе</a>
        <a href="/support?status=resolved" class="btn" style="background:#10B981;color:white">✅ Решено</a>
    </div>
    """
    
    # Таблица сообщений
    if not messages:
        messages_html = '<div class="card">Нет сообщений</div>'
    else:
        rows = ""
        for msg in messages:
            status_badge = {
                "new": '<span class="badge badge-green">🆕 Новый</span>',
                "in_progress": '<span class="badge" style="background:#FEF3C7;color:#D97706">⏳ В работе</span>',
                "resolved": '<span class="badge badge-green">✅ Решено</span>',
                "closed": '<span class="badge badge-gray">🔒 Закрыто</span>'
            }.get(msg["status"], f'<span class="badge badge-gray">{msg["status"]}</span>')
            
            username = msg.get("username") or f"ID:{msg['telegram_id']}"
            preview = msg["message_text"][:60] + "..." if len(msg["message_text"]) > 60 else msg["message_text"]
            created = fmt_date(msg["created_at"], short=True)
            
            reply_badge = ""
            if msg.get("admin_reply"):
                reply_badge = '<span class="badge badge-green">💬 Есть ответ</span>'
            
            assigned = msg.get("assigned_to") or "—"
            
            rows += f"""
            <tr>
                <td>
                    <a href="/support/{msg['id']}"><strong>#{msg['id']}</strong></a><br>
                    <span style="color:#6B7280;font-size:12px">{username}</span>
                </td>
                <td style="max-width:400px">
                    <div class="trigger-text">{preview}</div>
                </td>
                <td>{status_badge} {reply_badge}</td>
                <td>{assigned}</td>
                <td style="color:#6B7280;font-size:12px">{created}</td>
                <td>
                    <a href="/support/{msg['id']}" class="btn btn-blue" style="padding:4px 12px;font-size:12px">Открыть</a>
                </td>
            </tr>
            """
        
        messages_html = f"""
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Тикет</th>
                        <th>Сообщение</th>
                        <th>Статус</th>
                        <th>Исполнитель</th>
                        <th>Дата</th>
                        <th>Действие</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
    
    content = stats_html + filters_html + messages_html
    return page("💬 Сообщения поддержки", content, "messages")


@app.get("/support/{message_id}", response_class=HTMLResponse)
async def support_message_detail(request: Request, message_id: int):
    """Детальная страница сообщения поддержки."""
    msg = await db.get_support_message(message_id)
    
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    
    # Получаем историю переписки с этим пользователем
    history = await db.get_support_messages_by_user(msg["telegram_id"], limit=10)
    
    status_select = f"""
    <select name="status" onchange="this.form.submit()" style="padding:8px 12px;border-radius:8px;border:1px solid #D1D5DB;font-size:14px">
        <option value="new" {'selected' if msg['status'] == 'new' else ''}>🆕 Новый</option>
        <option value="in_progress" {'selected' if msg['status'] == 'in_progress' else ''}>⏳ В работе</option>
        <option value="resolved" {'selected' if msg['status'] == 'resolved' else ''}>✅ Решено</option>
        <option value="closed" {'selected' if msg['status'] == 'closed' else ''}>🔒 Закрыто</option>
    </select>
    """
    
    history_html = ""
    for h in history:
        if h["id"] == message_id:
            continue
        h_date = fmt_date(h["created_at"], short=True)
        h_preview = h["message_text"][:100] + "..." if len(h["message_text"]) > 100 else h["message_text"]
        history_html += f"""
        <div style="padding:12px;background:#F9FAFB;border-radius:8px;margin-bottom:8px">
            <div style="font-size:12px;color:#6B7280;margin-bottom:4px">#{h['id']} — {h_date}</div>
            <div style="font-size:14px">{h_preview}</div>
        </div>
        """
    
    reply_form = f"""
    <form method="post" action="/support/{message_id}/reply" style="margin-top:20px">
        <div style="margin-bottom:12px">
            <label style="display:block;font-size:13px;font-weight:600;color:#6B7280;margin-bottom:8px;text-transform:uppercase">
                Ответ пользователю
            </label>
            <textarea name="reply_text" rows="4" style="width:100%;padding:12px;border:1px solid #D1D5DB;border-radius:8px;font-size:14px;font-family:inherit" placeholder="Напиши ответ..."></textarea>
        </div>
        <button type="submit" class="btn btn-blue">💬 Отправить ответ</button>
    </form>
    """

    content = f"""
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:20px">
        <div>
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <div>
                        <h3 style="font-size:18px;margin-bottom:4px">Тикет #{msg['id']}</h3>
                        <div style="font-size:13px;color:#6B7280">
                            Пользователь: <strong>{msg.get('username') or f"ID:{msg['telegram_id']}"}</strong> |
                            TG ID: <code>{msg['telegram_id']}</code>
                        </div>
                    </div>
                    <form method="post" action="/support/{message_id}/status" style="display:flex;gap:8px">
                        {status_select}
                    </form>
                </div>

                <div style="background:#F3F4F6;padding:16px;border-radius:8px;margin-bottom:16px">
                    <div style="font-size:12px;color:#6B7280;margin-bottom:8px">Сообщение пользователя:</div>
                    <div style="font-size:15px;line-height:1.6">{msg['message_text']}</div>
                </div>

                {reply_form if not msg.get('admin_reply') else ''}

                {f'<div style="margin-top:16px;padding:16px;background:#ECFDF5;border-radius:8px"><div style="font-size:12px;color:#059669;margin-bottom:8px">✅ Ответ админа:</div><div style="font-size:15px;line-height:1.6">{msg["admin_reply"]}</div><div style="font-size:12px;color:#6B7280;margin-top:8px">Отвечал: {msg.get("assigned_to", "—")} | {fmt_date(msg.get("answered_at", ""), short=True)}</div></div>' if msg.get('admin_reply') else ''}
            </div>
            
            <div class="card" style="margin-top:20px">
                <h4 style="font-size:14px;margin-bottom:12px">📋 История переписки</h4>
                {history_html if history_html else '<div style="color:#6B7280;font-size:14px">Нет других обращений</div>'}
            </div>
        </div>
        
        <div>
            <div class="card">
                <h4 style="font-size:14px;margin-bottom:12px">ℹ️ Информация</h4>
                <div style="font-size:13px;line-height:2">
                    <div><strong>Статус:</strong> {msg['status']}</div>
                    <div><strong>Исполнитель:</strong> {msg.get('assigned_to') or 'Не назначен'}</div>
                    <div><strong>Создано:</strong> {fmt_date(msg['created_at'])}</div>
                    <div><strong>Обновлено:</strong> {fmt_date(msg['updated_at'])}</div>
                    {f'<div><strong>Отвечено:</strong> {fmt_date(msg["answered_at"])}</div>' if msg.get('answered_at') else ''}
                </div>
            </div>
            
            <div class="card" style="margin-top:16px">
                <h4 style="font-size:14px;margin-bottom:12px">⚡ Действия</h4>
                <div style="display:flex;flex-direction:column;gap:8px">
                    <a href="/support/{message_id}/assign" class="btn btn-blue">👤 Назначить на меня</a>
                    <a href="/support" class="btn" style="background:#6B7280;color:white">← Назад к списку</a>
                </div>
            </div>
        </div>
    </div>
    """
    
    return page(f"Тикет #{msg['id']}", content, "messages")


@app.post("/support/{message_id}/reply")
async def support_reply(message_id: int, request: Request, reply_text: str = Form(...)):
    """Отправить ответ пользователю."""
    # Получаем сообщение
    msg = await db.get_support_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    
    # Сохраняем ответ
    await db.reply_to_support_message(
        message_id=message_id,
        admin_reply=reply_text,
        admin_username="admin"  # TODO: брать из сессии
    )
    
    # Отправляем ответ пользователю в Telegram
    if BOT_TOKEN:
        from aiogram import Bot
        from aiogram.enums import ParseMode
        bot = Bot(token=BOT_TOKEN, default_bot_properties={"parse_mode": ParseMode.HTML})
        try:
            await bot.send_message(
                msg["telegram_id"],
                f"💬 <b>Ответ на ваше обращение #{message_id}</b>\n\n"
                f"{reply_text}\n\n"
                f"<i>Если есть ещё вопросы — пишите!</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send support reply to {msg['telegram_id']}: {e}")
        finally:
            await bot.session.close()
    
    return RedirectResponse(f"/support/{message_id}", status_code=302)


@app.post("/support/{message_id}/status")
async def support_update_status(message_id: int, request: Request, status: str = Form(...)):
    """Обновить статус тикета."""
    await db.update_support_status(message_id, status)
    return RedirectResponse(f"/support/{message_id}", status_code=302)


@app.get("/support/{message_id}/assign")
async def support_assign(message_id: int, request: Request):
    """Назначить тикет на текущего админа."""
    await db.assign_support_message(message_id, "admin")  # TODO: брать из сессии
    return RedirectResponse(f"/support/{message_id}", status_code=302)


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    env = os.getenv("ENVIRONMENT", "production")
    port = 8081 if env == "test" else 8080
    
    env_label = "🧪 TEST" if env == "test" else "⚔️ PRODUCTION"
    
    print("")
    print("╔═══════════════════════════════════════════════════════════╗")
    print(f"║         🚀 Admin Panel — {env_label:<26} ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print("")
    print(f"  🌐 URL:      http://localhost:{port}/admin")
    print(f"  📊 Порт:     {port}")
    print(f"  🗄  База:     {DB_PATH}")
    print(f"  🔑 Логин:    {ADMIN_USERNAME}")
    print(f"  🔑 Пароль:   {ADMIN_PASSWORD}")
    print("")
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

