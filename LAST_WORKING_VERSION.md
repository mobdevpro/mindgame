# 🏷 Last Working Version

**Tag:** `last-working-version-2026-03-17`

**Date:** March 17, 2026

---

## ✅ Fixed Issues

| Issue | Solution |
|---|---|
| **DB_PATH Race Condition** | Added `FIXED_DB_PATH` constant that is fixed at bot startup |
| **User Switching Bug** | `database.py` now uses `FIXED_DB_PATH` instead of `DB_PATH` |
| **Telegram Cache** | WebApp now clears cache on load |
| **Wrong Referral Code** | Database restored from backup, correct code: `6KH99EBB` |

---

## 🔧 Configuration

### Environment
```bash
ENVIRONMENT=production
DB_PATH=game.db
FIXED_DB_PATH=game.db
```

### Architecture
- **Single Database:** `game.db` (test.db disabled)
- **Test Bot:** Disabled
- **Production Bot:** Active

---

## 📱 Features

| Feature | Status |
|---|---|
| Trigger Recording | ✅ Working |
| Trigger Patterns (AI) | ✅ Working |
| Diary | ✅ Working |
| Tasks | ✅ Working |
| Stop Mode | ✅ Working |
| Shop | ✅ Working |
| Support Messages | ✅ Working |
| Referral System | ✅ Working |
| WebApp (Mini App) | ✅ Working |
| Admin Panel | ✅ Working |

---

## 🎯 User Account

| Field | Value |
|---|---|
| **Telegram ID** | `343933093` |
| **Username** | `vadyog` |
| **Referral Code** | `6KH99EBB` |
| **Balance** | `697 TRGR` |

---

## 🔍 Diagnostic Commands

### For Users
```
/mydb — Show current database and user info
/start — Restart bot
/help — Show help message
```

### For Admins
```bash
# Check bot status
systemctl status mindgame-bot

# Restart bot
systemctl restart mindgame-bot

# Check database
sqlite3 /opt/mindgame/game.db "SELECT * FROM users WHERE telegram_id = 343933093"

# Check logs
journalctl -u mindgame-bot -n 50 --no-pager
```

---

## 📊 Database Tables

| Table | Purpose |
|---|---|
| `users` | User accounts |
| `triggers` | Trigger records |
| `trigger_reflections` | Trigger reflections |
| `diary_entries` | Diary entries |
| `tasks` | User tasks |
| `rewards_log` | Points history |
| `achievements` | Achievement definitions |
| `user_achievements` | User achievements |
| `notification_settings` | Notification preferences |
| `products` | Shop products |
| `purchases` | Purchase history |
| `support_messages` | Support tickets |
| `pattern_analyses` | AI pattern analysis |
| `trigger_clusters` | Trigger clusters |
| `menu_settings` | Menu button settings |
| `message_templates` | Message templates |
| `points_config` | Points configuration |
| `schema_migrations` | Database migrations |

---

## 🚀 Deployment

### Update Server
```bash
cd /opt/mindgame
git pull
git checkout last-working-version-2026-03-17
sed -i 's/ENVIRONMENT=test/ENVIRONMENT=production/g' .env
systemctl restart mindgame-bot
```

### Verify
```bash
# Check bot status
systemctl is-active mindgame-bot

# Check database
sqlite3 /opt/mindgame/game.db "SELECT referral_code FROM users WHERE telegram_id = 343933093"

# Should return: 6KH99EBB
```

---

## 📝 Notes

- **Test bot disabled** — using single database architecture
- **test.db archived** — located at `test.db.archived`
- **FIXED_DB_PATH** prevents database switching during rapid requests
- **/mydb command** added for diagnostics

---

## 🔗 Links

| Service | URL |
|---|---|
| **Production Bot** | [@Vadimbagautdinov_bot](https://t.me/Vadimbagautdinov_bot) |
| **Production Admin** | https://vadbag.su/admin |
| **WebApp** | https://vadbag.su/app |
| **GitHub** | https://github.com/mobdevpro/mindgame |

---

**Status:** ✅ Stable and Working

---

## 🎤 Vosk Voice Model

### Installation
```bash
cd /opt/mindgame
bash setup_vosk.sh
```

### Manual Installation
```bash
cd /opt/mindgame
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip
rm vosk-model-small-ru-0.22.zip
systemctl restart mindgame-bot
```

### Why It Disappears
- Model is NOT in git (50MB file)
- Deleted during server cleanups (`rm -rf`)
- Not restored from backups (only database is backed up)

### Prevention
- Model is in `.gitignore` to prevent accidental commits
- Setup script `setup_vosk.sh` for easy reinstallation
- Documentation in this file

### Verification
1. Send voice message to bot
2. Bot should recognize text
3. Trigger should be created automatically

