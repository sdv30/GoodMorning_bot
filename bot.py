#!/usr/bin/env python3
"""
Семейный утренний Telegram-бот.

Режимы работы:
  1. Telegram polling (интерактивный): бот слушает команды /morning, /calendar, /help
  2. CLI (cron): python3 bot.py morning | calendar | health

Для polling-режима нужен .env с TELEGRAM_TOKEN и CHAT_ID.
"""

import sys
import os
import time
import signal
import json
import requests
import datetime
import pytz
import logging

# Настройка логирования
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "bot.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from config import (
    TELEGRAM_TOKEN, 
    CHAT_ID, 
    TELEGRAM_MAX_MESSAGE_LENGTH,
    POLLING_ERROR_RETRY_DELAY,
)
from services import (
    get_weather_forecast,
    get_random_image_url,
    get_calend_holidays,
    get_ignio_astrology,
    format_morning_post_via_openai,
    format_astrology_via_openai,
    generate_wisdom_for_galina,
    format_calendar_via_openai,
)

# ---------------------------------------------------------------------------
# Telegram API helper
# ---------------------------------------------------------------------------

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
LAST_UPDATE_ID_FILE = os.path.join(os.path.dirname(__file__), ".last_update_id")

# Graceful shutdown handling
shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    logger.info("Shutdown requested...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def tg_send_message(chat_id: str, text: str, parse_mode: str = "HTML"):
    """Отправляет текстовое сообщение."""
    url = f"{TG_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    logger.info(f"SEND message to {chat_id}: {text[:100]}...")
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    logger.info(f"SEND OK to {chat_id}")
    return resp.json()


def tg_send_long_message(chat_id: str, text: str, parse_mode: str = "HTML"):
    """Безопасно отправляет длинный текст частями (лимит Telegram ~4096 символов)."""
    if not text:
        return
    max_len = TELEGRAM_MAX_MESSAGE_LENGTH
    start = 0
    while start < len(text):
        chunk = text[start:start + max_len]
        tg_send_message(chat_id, chunk, parse_mode=parse_mode)
        start += max_len


def tg_send_photo(chat_id: str, photo_url: str, caption: str = "", parse_mode: str = "HTML"):
    """Отправляет фото с подписью."""
    url = f"{TG_API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    logger.info(f"SEND photo to {chat_id}: {photo_url}")
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    logger.info(f"SEND photo OK to {chat_id}")
    return resp.json()


def tg_get_updates(offset: int = 0, timeout: int = 30) -> list:
    """Получает обновления через getUpdates."""
    url = f"{TG_API}/getUpdates"
    params = {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": ["message"],
    }
    logger.debug(f"GET updates offset={offset}")
    resp = requests.get(url, params=params, timeout=timeout + 5)
    resp.raise_for_status()
    result = resp.json().get("result", [])
    logger.debug(f"Got {len(result)} updates")
    return result


def _load_last_update_id() -> int:
    try:
        with open(LAST_UPDATE_ID_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _save_last_update_id(uid: int):
    with open(LAST_UPDATE_ID_FILE, "w") as f:
        f.write(str(uid))


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def get_yakutsk_now():
    tz = pytz.timezone("Asia/Yakutsk")
    return datetime.datetime.now(tz)


def get_date_string():
    now = get_yakutsk_now()
    weekdays = {
        0: "Понедельник", 1: "Вторник", 2: "Среда",
        3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье",
    }
    return f"{now.strftime('%d.%m.%Y')}, {weekdays[now.weekday()]}"


def run_health_check() -> int:
    """
    Базовая проверка здоровья без внешних API-вызовов.
    Возвращает 0 при успехе и 1 при проблемах.
    """
    logger.info("[health] Запуск проверки состояния...")
    errors = []

    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN не задан")
    if not CHAT_ID:
        errors.append("CHAT_ID не задан")
    if not TG_API.startswith("https://api.telegram.org/bot"):
        errors.append("Неверный формат TG_API")

    try:
        now = get_yakutsk_now()
        if now.tzinfo is None:
            errors.append("Не удалось получить tz-aware время Asia/Yakutsk")
    except Exception as exc:
        errors.append(f"Ошибка часов Yakutsk: {exc}")

    if errors:
        for err in errors:
            logger.error(f"[health] {err}")
        logger.error("[health] FAILED")
        return 1

    logger.info("[health] OK")
    return 0


# ---------------------------------------------------------------------------
# Справка
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "👋 <b>Семейный утренний бот</b>\n\n"
    "Я автоматически отправляю сообщения каждый день:\n\n"
    "🕢 <b>07:30 — Утренний пост</b>\n"
    "  • Дата, день недели и бодрое приветствие\n"
    "  • Красивое фото из Unsplash\n"
    "  • Подробная погода в Якутске (Утро / День / Вечер)\n"
    "  • Прогноз для Людмилы (Овен) — совет дня от профи\n"
    "  • Остроумное пожелание для Галины\n\n"
    "🕗 <b>08:00 — Народный календарь</b>\n"
    "  • Суть праздника из Calend.ru\n"
    "  • 2-3 народные приметы\n"
    "  • Совет «в духе предков»\n\n"
    "📋 <b>Команды для ручной проверки:</b>\n"
    "/morning — Утренний пост\n"
    "/calendar — Народный календарь\n"
    "/help — Эта справка"
)


# ---------------------------------------------------------------------------
# ЗАДАЧА 1: morning
# ---------------------------------------------------------------------------

def run_morning(chat_id: str = None):
    """Утренний пост: дата, погода, картинка, астрология, пожелание."""
    cid = chat_id or CHAT_ID
    logger.info("[morning] Запуск утреннего поста...")
    date_str = get_date_string()
    logger.info(f"[morning] Date: {date_str}")

    weather_data = get_weather_forecast()
    logger.info(f"[morning] Weather data: {json.dumps(weather_data, ensure_ascii=False) if weather_data else 'NONE'}")
    
    image_url = get_random_image_url()
    logger.info(f"[morning] Image URL: {image_url}")

    morning_text = format_morning_post_via_openai(date_str, weather_data, image_url)
    logger.info(f"[morning] AI output length: {len(morning_text) if morning_text else 0}")
    if morning_text:
        logger.info(f"[morning] AI output preview: {morning_text[:300]}...")
    
    if not morning_text:
        morning_text = (
            f"☀️ Доброе утро!\n\n"
            f"📅 {date_str}\n\n"
            f"Якутск, просыпайтесь. Кофе ждёт, день не будет ждать."
        )
        logger.warning("[morning] AI returned None, using fallback")

    try:
        if image_url:
            tg_send_photo(cid, photo_url=image_url, caption=morning_text)
            logger.info("[morning] ✅ Фото + приветствие отправлено.")
        else:
            tg_send_long_message(cid, morning_text)
            logger.warning("[morning] ⚠️ Картинка недоступна, отправлен только текст")
    except Exception as e:
        logger.error(f"[morning] ❌ Ошибка фото: {e}")
        try:
            tg_send_long_message(cid, morning_text)
        except Exception as e2:
            logger.error(f"[morning] ❌ Ошибка fallback-текста: {e2}")

    # Астрология для Людмилы
    try:
        ignio_raw = get_ignio_astrology("aries")
        logger.info(f"[morning] Ignio raw: {ignio_raw[:200] if ignio_raw else 'NONE'}...")
        astrology_text = format_astrology_via_openai(ignio_raw)
        logger.info(f"[morning] Astro output: {astrology_text[:300] if astrology_text else 'NONE'}...")
        if astrology_text:
            tg_send_long_message(cid, text=astrology_text)
            logger.info("[morning] ✅ Гороскоп отправлен.")
        else:
            logger.warning("[morning] ⚠️ Гороскоп недоступен")
    except Exception as e:
        logger.error(f"[morning] ❌ Ошибка гороскопа: {e}")

    # Пожелание для Галины
    try:
        wisdom = generate_wisdom_for_galina()
        logger.info(f"[morning] Wisdom AI output: {wisdom[:300] if wisdom else 'NONE'}...")
        if wisdom:
            tg_send_long_message(cid, text=wisdom)
            logger.info("[morning] ✅ Пожелание для Галины отправлено.")
    except Exception as e:
        logger.error(f"[morning] ❌ Ошибка пожелания: {e}")

    logger.info("[morning] Готово!")


# ---------------------------------------------------------------------------
# ЗАДАЧА 2: calendar
# ---------------------------------------------------------------------------

def run_calendar(chat_id: str = None):
    """Народный календарь с приметами."""
    cid = chat_id or CHAT_ID
    logger.info("[calendar] Запуск поста о праздниках...")

    holidays = get_calend_holidays()
    logger.info(f"[calendar] Holidays: {len(holidays)} items: {[h['title'][:50] for h in holidays]}")
    
    calendar_text = format_calendar_via_openai(holidays)
    logger.info(f"[calendar] AI output length: {len(calendar_text) if calendar_text else 0}")
    if calendar_text:
        logger.info(f"[calendar] AI output preview: {calendar_text[:300]}...")

    if not calendar_text:
        calendar_text = (
            "📅 <b>Народный календарь</b>\n\n"
            "Сегодняшний день в народной традиции связан с переменами в погоде. "
            "Наши предки в это время наблюдали за природой: если ветер дует с юга — "
            "будет тёплая погода, если с севера — жди похолодания. "
            "Хороший день для начала новых дел и домашних забот. "
            "По народной примете, кто сегодня рано встаёт — тому весь год удача сопутствует. "
            "А ещё говорили: «Весенний день год кормит» — не теряй времени зря."
        )
        logger.warning("[calendar] AI returned None, using fallback")

    try:
        tg_send_long_message(cid, text=calendar_text)
        logger.info("[calendar] ✅ Календарь отправлен.")
    except Exception as e:
        logger.error(f"[calendar] ❌ Ошибка: {e}")

    logger.info("[calendar] Готово!")


# ---------------------------------------------------------------------------
# POLLING: обработчик команд из Telegram
# ---------------------------------------------------------------------------

def handle_message(message: dict):
    """Обрабатывает одно сообщение из Telegram."""
    msg_text = message.get("text", "").strip()
    chat_id = str(message["chat"]["id"])
    chat_type = message["chat"].get("type", "unknown")
    from_name = message.get("from", {}).get("first_name", "unknown")

    logger.info(f"RECV: from={from_name} chat_id={chat_id} type={chat_type} text='{msg_text}'")

    # Разрешаем: наш групповой чат ИЛИ личные сообщения
    allowed_chats = {CHAT_ID}
    if chat_type == "private":
        allowed_chats.add(chat_id)

    if chat_id not in allowed_chats:
        logger.info(f"IGNORED: chat_id={chat_id} not in allowed={allowed_chats}")
        return

    cmd = msg_text.lower().lstrip("/")
    logger.info(f"COMMAND: {cmd}")

    if cmd == "morning":
        tg_send_message(chat_id, "Formiruyu utrenniy post...")
        run_morning(chat_id)
    elif cmd == "calendar":
        tg_send_message(chat_id, "Ishchu prazdniki i primety...")
        run_calendar(chat_id)
    elif cmd in ("help", "start"):
        tg_send_message(chat_id, text=HELP_TEXT)
    else:
        tg_send_message(
            chat_id,
            text="Unknown command. Send /help for available commands."
        )


def polling_loop():
    """
    Бесконечный цикл polling + встроенный планировщик по Якутскому времени.
    
    ВАЖНО: Сервер может работать в любом часовом поясе. Все сравнения времени делаются
    строго в часовом поясе Asia/Yakutsk (UTC+9).
    """
    global shutdown_requested
    
    offset = _load_last_update_id() + 1
    
    yakutsk_tz = pytz.timezone("Asia/Yakutsk")
    
    # Логируем часовые пояса при старте
    now_utc = datetime.datetime.utcnow()
    now_yakutsk = datetime.datetime.now(yakutsk_tz)
    logger.info(f"Bot started polling, offset={offset}")
    logger.info(f"Server time (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Yakutsk time (UTC+9): {now_yakutsk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Корректно вычисляем UTC эквивалент для логов
    morning_utc = (now_yakutsk.replace(hour=7, minute=30, second=0, microsecond=0)
                   .astimezone(pytz.utc))
    logger.info(f"Schedule: morning=07:30 Yakutsk (= {morning_utc.strftime('%H:%M')} UTC)")

    # Планировщик: отслеживаем, какие задачи уже выполнены сегодня
    # Формат: {date_str: {task_key: {"attempted": bool, "last_attempt": datetime}}}
    scheduled_tasks = {}

    # Расписание задач по якутскому времени (час, минута)
    TASK_SCHEDULE = [
        (7, 30, "morning", run_morning),
        (8, 0, "calendar", run_calendar),
    ]

    while not shutdown_requested:
        try:
            # --- Планировщик ---
            # ВСЕГДА получаем время в Asia/Yakutsk
            now_yakutsk = datetime.datetime.now(yakutsk_tz)
            today_str = now_yakutsk.strftime("%Y-%m-%d")
            current_hour = now_yakutsk.hour
            current_min = now_yakutsk.minute

            # Инициализируем сегодняшние задачи
            if today_str not in scheduled_tasks:
                scheduled_tasks[today_str] = {}
                logger.info(f"SCHEDULER: New day {today_str} (Yakutsk), resetting task list")
                # Удаляем вчерашние записи (экономия памяти)
                yesterday_str = (now_yakutsk - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                if yesterday_str in scheduled_tasks:
                    del scheduled_tasks[yesterday_str]

            completed_today = scheduled_tasks[today_str]

            for hour, minute, task_name, task_func in TASK_SCHEDULE:
                task_key = f"{hour:02d}:{minute:02d}"
                
                # Пропускаем уже выполненные задачи
                if task_key in completed_today and completed_today[task_key].get("attempted"):
                    continue

                # Проверяем, наступило ли время задачи (с окном в 1 минуту)
                if current_hour == hour and current_min == minute:
                    task_info = completed_today.get(task_key, {})
                    
                    # Если задача ещё не尝试ована сегодня, выполняем
                    if not task_info.get("attempted"):
                        logger.info(f"SCHEDULER: Triggering {task_name} at {now_yakutsk.strftime('%H:%M')} Yakutsk (UTC+9)")
                        completed_today[task_key] = {"attempted": True, "last_attempt": now_yakutsk}
                        try:
                            task_func()
                            logger.info(f"SCHEDULER: {task_name} completed successfully")
                        except Exception as e:
                            logger.error(f"SCHEDULER: {task_name} failed: {e}")
                            # Задача помечена как attempted, повтор только на следующий день

            # --- Polling ---
            updates = tg_get_updates(offset=offset, timeout=30)
            
            # Обрабатываем все обновления, сохраняем max update_id
            max_update_id = offset - 1
            for update in updates:
                update_id = update["update_id"]
                max_update_id = max(max_update_id, update_id)
                
                message = update.get("message")
                if message and "text" in message:
                    try:
                        handle_message(message)
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        # Продолжаем обработку других обновлений
            
            # Сохраняем offset только после обработки всех обновлений
            if max_update_id >= offset:
                _save_last_update_id(max_update_id)
                offset = max_update_id + 1
                
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(POLLING_ERROR_RETRY_DELAY)
    
    logger.info("Bot shutdown complete")


# ---------------------------------------------------------------------------
# CLI: обработка аргументов командной строки
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) >= 2:
        # CLI-режим (для cron)
        command = sys.argv[1].lower()
        if command == "morning":
            run_morning()
        elif command == "calendar":
            run_calendar()
        elif command == "health":
            sys.exit(run_health_check())
        else:
            print(f"Неизвестная команда: {command}")
            print("Допустимые: morning, calendar, health")
            sys.exit(1)
    else:
        # Polling-режим (интерактивный бот)
        logger.info("=" * 50)
        logger.info("Bot started in polling mode")
        logger.info("Commands: /morning, /calendar, /help")
        logger.info("=" * 50)
        polling_loop()


if __name__ == "__main__":
    main()
