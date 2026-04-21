from __future__ import annotations
from typing import Optional
import logging
import json
import requests
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from openai import OpenAI
from config import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    OPENWEATHER_API_KEY,
    UNSPLASH_ACCESS_KEY,
    YAKUTSK_LAT,
    YAKUTSK_LON,
    HTTP_TIMEOUT,
    HTTP_RETRIES,
    AI_TEMPERATURE,
)

logger = logging.getLogger(__name__)
# Ensure logger actually outputs — add a StreamHandler if no handlers
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# Create session with retry logic
def create_session_with_retries(retries=HTTP_RETRIES, backoff_factor=1):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session_with_retries()

# Lazy initialization of AI client
_client = None

def get_ai_client():
    global _client
    if _client is None:
        if not AI_API_KEY:
            raise ValueError("AI_API_KEY not configured")
        _client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
    return _client


# ---------------------------------------------------------------------------
# 1. ПОГОДА — OpenWeatherMap Forecast API
# ---------------------------------------------------------------------------

def get_weather_forecast():
    """
    Прогноз погоды в Якутске через OpenWeatherMap forecast.
    Возвращает dict: {morning: {temp, desc}, day: {...}, evening: {...}}
    
    ВАЖНО: OpenWeatherMap отдаёт данные в UTC. Якутск = UTC+9.
    Конвертируем каждый слот в Asia/Yakutsk перед фильтрацией.
    """
    try:
        import pytz
        from datetime import datetime, timedelta
        
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={YAKUTSK_LAT}&lon={YAKUTSK_LON}"
            f"&appid={OPENWEATHER_API_KEY}"
            f"&units=metric&lang=ru"
        )
        logger.info(f"[WEATHER] Request: {url}")
        resp = session.get(url, timeout=HTTP_TIMEOUT)
        logger.info(f"[WEATHER] Response HTTP {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        
        # Валидация структуры ответа
        if "list" not in data:
            logger.error(f"[WEATHER] Invalid response structure: {list(data.keys())}")
            return None
        
        logger.info(f"[WEATHER] Got {len(data.get('list', []))} forecast slots")

        yakutsk_tz = pytz.timezone("Asia/Yakutsk")
        now_yakutsk = datetime.now(yakutsk_tz)
        today_yakutsk = now_yakutsk.date()
        logger.info(f"[WEATHER] Now in Yakutsk: {now_yakutsk.isoformat()}, today: {today_yakutsk}")

        morning_slots = []
        day_slots = []
        evening_slots = []

        for item in data.get("list", []):
            # OpenWeatherMap dt_txt — это UTC. Конвертируем в Якутск.
            dt_utc = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
            dt_utc = pytz.utc.localize(dt_utc)
            dt_yakutsk = dt_utc.astimezone(yakutsk_tz)
            
            if dt_yakutsk.date() != today_yakutsk:
                continue
            
            hour = dt_yakutsk.hour
            entry = {
                "temp": round(item["main"]["temp"]),
                "desc": item["weather"][0]["description"].capitalize(),
                "yakutsk_time": dt_yakutsk.strftime("%H:%M"),
            }
            logger.info(f"[WEATHER] Slot: {item['dt_txt']} UTC -> {dt_yakutsk.strftime('%H:%M')} Yakutsk, {entry['temp']}C, {entry['desc']}")
            
            if 6 <= hour <= 11:
                morning_slots.append(entry)
            elif 12 <= hour <= 17:
                day_slots.append(entry)
            elif 18 <= hour <= 23:  # Исправлено: только вечерние часы, без ранних утренних
                evening_slots.append(entry)

        def avg_period(slots):
            if not slots:
                return {"temp": "н/д", "desc": "Нет данных"}
            avg_temp = round(sum(s["temp"] for s in slots) / len(slots))
            descs = [s["desc"] for s in slots]
            most_common = max(set(descs), key=descs.count)
            return {"temp": avg_temp, "desc": most_common}

        result = {
            "morning": avg_period(morning_slots),
            "day": avg_period(day_slots),
            "evening": avg_period(evening_slots),
        }
        logger.info(f"[WEATHER] Result: {json.dumps(result, ensure_ascii=False)}")
        return result
    except requests.exceptions.Timeout:
        logger.error("[WEATHER] Request timeout")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"[WEATHER] HTTP error {e.response.status_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"[WEATHER] Error: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. КАРТИНКИ — Unsplash API
# ---------------------------------------------------------------------------

def get_random_image_url():
    """Случайная картинка с Unsplash."""
    try:
        url = "https://api.unsplash.com/photos/random"
        params = {
            "query": "morning nature",
            "orientation": "landscape",
            "client_id": UNSPLASH_ACCESS_KEY,
        }
        logger.info(f"[UNSPLASH] Request: {url}")
        resp = session.get(url, params=params, timeout=HTTP_TIMEOUT)
        logger.info(f"[UNSPLASH] Response HTTP {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        
        # Валидация структуры ответа
        if "urls" not in data:
            logger.error(f"[UNSPLASH] Invalid response structure: {list(data.keys())}")
            return "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200"
        
        img_url = data.get("urls", {}).get("regular") or data.get("urls", {}).get("full")
        if not img_url:
            logger.warning("[UNSPLASH] No valid URL found in response")
            return "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200"
        
        logger.info(f"[UNSPLASH] Got URL: {img_url}")
        return img_url
    except requests.exceptions.Timeout:
        logger.error("[UNSPLASH] Request timeout")
        return "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200"
    except requests.exceptions.HTTPError as e:
        logger.error(f"[UNSPLASH] HTTP error {e.response.status_code}: {e}")
        return "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200"
    except Exception as e:
        logger.error(f"[UNSPLASH] Error: {type(e).__name__}: {e}")
        return "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200"


# ---------------------------------------------------------------------------
# 3. ПРАЗДНИКИ — Calend.ru RSS
# ---------------------------------------------------------------------------

def get_calend_holidays():
    """RSS с Calend.ru — праздники и приметы."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (GoodMorningBot/1.0)"}
        logger.info(f"[CALEND] Request: https://www.calend.ru/img/export/calend.rss")
        resp = session.get(
            "https://www.calend.ru/img/export/calend.rss",
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
        logger.info(f"[CALEND] Response HTTP {resp.status_code}, Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        
        # Check if we got HTML instead of XML
        content_preview = resp.text[:200]
        if "<html" in content_preview.lower():
            logger.error(f"[CALEND] Got HTML instead of XML! Body: {content_preview}")
            return []
        
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        today_holidays = []

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            desc = item.findtext("description", "").strip()
            if title:
                today_holidays.append({"title": title, "description": desc})

        if not today_holidays:
            for item in root.findall(".//item")[:3]:
                today_holidays.append({
                    "title": item.findtext("title", ""),
                    "description": item.findtext("description", ""),
                })

        result = today_holidays[:5]
        logger.info(f"[CALEND] Got {len(result)} holidays: {[h['title'][:50] for h in result]}")
        return result
    except requests.exceptions.Timeout:
        logger.error("[CALEND] Request timeout")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"[CALEND] HTTP error {e.response.status_code}: {e}")
        return []
    except Exception as e:
        logger.error(f"[CALEND] Error: {type(e).__name__}: {e}")
        return []


# ---------------------------------------------------------------------------
# 4. АСТРОЛОГИЯ — Ignio.com XML
# ---------------------------------------------------------------------------

def get_ignio_astrology(sign="aries"):
    """
    Забираем гороскоп с 1001goroskop.ru (XML от Ignio больше не работает).
    Название функции оставляем старым, чтобы не переписывать bot.py.
    """
    url = f"https://1001goroskop.ru/?znak={sign}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        logger.info(f"[GOROSKOP] Request: {url}")
        response = session.get(url, headers=headers, timeout=10)
        logger.info(f"[GOROSKOP] Response HTTP {response.status_code}, length: {len(response.content)} bytes")
        
        # Check for Cloudflare using status code and headers
        if response.status_code in [503, 403] and "cf-ray" in response.headers:
            logger.error("[GOROSKOP] Cloudflare protection detected")
            return None
        
        response.raise_for_status()

        # Парсим текст гороскопа с помощью регулярки.
        # На 1001goroskop текст лежит в блоке с itemprop="description"
        import re
        match = re.search(r'<div itemprop="description">(.*?)</div>', response.text, re.DOTALL | re.IGNORECASE)

        if match:
            raw_text = match.group(1)
            clean_text = re.sub(r'<[^>]+>', ' ', raw_text)
            clean_text = ' '.join(clean_text.split())
            logger.info(f"[GOROSKOP] Found text ({len(clean_text)} chars): {clean_text[:200]}...")
            return clean_text

        logger.warning(f"[GOROSKOP] Regex did not find horoscope block. HTML preview: {response.text[:500]}")
        return None

    except requests.exceptions.Timeout:
        logger.error("[GOROSKOP] Request timeout")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"[GOROSKOP] HTTP error {e.response.status_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"[GOROSKOP] Error: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# 5. AI-РЕДАКТОР (Claude Haiku через awstore)
# ---------------------------------------------------------------------------

def _ai_call(system_prompt: str, user_prompt: str, max_tokens: int = 1200) -> Optional[str]:
    """Универсальный вызов AI с автоматическим добавлением текущей даты в system prompt."""
    try:
        import pytz
        from datetime import datetime
        
        # Получаем клиент AI
        ai_client = get_ai_client()
        
        yakutsk_tz = pytz.timezone("Asia/Yakutsk")
        now_yakutsk = datetime.now(yakutsk_tz)
        current_date_info = now_yakutsk.strftime("%d %B %Y года, %A").replace("Monday", "понедельник").replace("Tuesday", "вторник").replace("Wednesday", "среда").replace("Thursday", "четверг").replace("Friday", "пятница").replace("Saturday", "суббота").replace("Sunday", "воскресенье")
        
        # Добавляем дату в начало system prompt
        enhanced_system = f"Сейчас {current_date_info}. {system_prompt}"
        
        logger.info(f"[AI INPUT] system: {enhanced_system[:500]}")
        logger.info(f"[AI INPUT] user: {user_prompt[:500]}")
        logger.info(f"[AI] model={AI_MODEL}, max_tokens={max_tokens}")
        
        response = ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=AI_TEMPERATURE,
            max_tokens=max_tokens,
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"[AI OUTPUT] ({len(result)} chars): {result[:500]}")
        return result
    except requests.exceptions.Timeout:
        logger.error(f"[AI ERROR] Request timeout after {max_tokens} tokens")
        return None
    except requests.exceptions.HTTPError as e:
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 429:
                logger.error("[AI ERROR] Rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("[AI ERROR] Invalid API key")
            else:
                logger.error(f"[AI ERROR] HTTP {e.response.status_code}: {e}")
        else:
            logger.error(f"[AI ERROR] HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"[AI ERROR] Unexpected error: {type(e).__name__}: {e}")
        return None


def format_morning_post_via_openai(date_str, weather_data, image_url):
    """Формирует бодрый утренний пост через Claude Haiku."""
    weather_context = ""
    if weather_data:
        m = weather_data.get("morning", {})
        d = weather_data.get("day", {})
        e = weather_data.get("evening", {})
        weather_context = (
            f"Утром: {m.get('temp', 'н/д')}°C, {m.get('desc', 'н/д')}\n"
            f"Днём: {d.get('temp', 'н/д')}°C, {d.get('desc', 'н/д')}\n"
            f"Вечером: {e.get('temp', 'н/д')}°C, {e.get('desc', 'н/д')}"
        )
    else:
        weather_context = "Данные о погоде недоступны."

    system = (
        "Ты — редактор семейного утреннего Telegram-чата. "
        "Пишешь живо, бодро, с лёгкой иронией. Без подхалимства, без «волшебных звёзд», "
        "без пустых фраз типа «всё будет отлично». "
        "Если погода плохая — говори прямо. Если хорошая — отметь без восторгов. "
        "Эмодзи — дозировано, 2-4 штуки."
    )
    user = f"""Сегодня {date_str}. Вот факты:

ПОГОДА В ЯКУТСКЕ:
{weather_context}

Напиши утреннее сообщение для семейного чата.
Обязательно включи:
1. Дату и день недели.
2. Бодрое приветствие всем участникам.
3. Прогноз погоды по периодам (утром, днём, вечером) — используй ТОЛЬКО данные выше.
4. Эмодзи — умеренно.

НЕ выдумывай факты о погоде."""

    return _ai_call(system, user, max_tokens=1000)


def format_astrology_via_openai(ignio_text):
    """
    Возвращает оригинальный астрологический прогноз с 1001goroskop.ru БЕЗ AI-перефразирования.
    
    ВАЖНО: прогноз на сайте статичен в течение суток. AI каждый раз генерирует
    разные формулировки, что вводит пользователей в заблуждение.
    Поэтому отдаём оригинальный текст с минимальным оформлением.
    """
    if not ignio_text:
        return None

    return (
        f"⭐ <b>Гороскоп для Людмилы (Овен)</b>\n\n"
        f"{ignio_text}"
    )


def generate_wisdom_for_galina():
    """Развёрнутая ироничная мудрость для Галины через Claude Haiku."""
    system = (
        "Ты — автор в стиле Ларошфуко, Чехова и современных ироничных мыслителей. "
        "Пишешь остроумные, парадоксальные мысли. "
        "Это НЕ тост из интернета и НЕ цитата из паблика ВК. "
        "Пиши по-русски, с лёгкой иронией."
    )
    user = (
        "Напиши для Галины на сегодня развёрнутое остроумное пожелание или парадоксальную мысль. "
        "ОБЪЁМ: 3-5 предложений, 40-80 слов. Разверни мысль, приведи пример или аналогию. "
        "Без банальностей. Основная идея - вера в себя и мотивация к действию, но не явно а мягко. Эмодзи — максимум одно."
    )

    return _ai_call(system, user, max_tokens=400)


def format_calendar_via_openai(holidays_list):
    """Развёрнутый пост о праздниках и приметах через Claude Haiku."""
    if not holidays_list:
        return None

    holidays_text = "\n".join(
        f"- {h['title']}: {h['description']}" for h in holidays_list
    )

    system = (
        "Ты — редактор семейного чата. Расскажи о праздниках и народных приметах "
        "подробно, живо, с иронией, но уважительно к традициям. Количество знаков не менее 250"
        "Пиши по-русски."
    )
    user = f"""Вот праздники и приметы на сегодня из календаря:

{holidays_text}

Создай развёрнутое сообщение для семейного чата.
Обязательно включи:
1. Суть дня — что празднуем. Если праздников несколько то пиши каждый с новой строки.
2. 2-3 яркие народные приметы (на что смотреть, чего ждать от природы).
3. Совет «в духе предков» (что можно и нельзя делать).
4. Эмодзи — умеренно, 3-5 штук.

ОБЪЁМ: 3-5 абзаца, 150 слов минимум.
Без пустых фраз типа «каждый день — повод для радости»."""

    return _ai_call(system, user, max_tokens=1200)


# ---------------------------------------------------------------------------
# 6. НОВОСТИ — RSS Lenta.ru и Ysia.ru
# ---------------------------------------------------------------------------

def _parse_rss_feed(url: str, user_agent: str = "Mozilla/5.0 (GoodMorningBot/1.0)") -> list:
    """Парсит RSS-ленту."""
    try:
        headers = {"User-Agent": user_agent}
        logger.info(f"[RSS] Request: {url}")
        resp = session.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        logger.info(f"[RSS] Response HTTP {resp.status_code}")
        
        # Check for HTML
        content_preview = resp.text[:200]
        if "<html" in content_preview.lower():
            logger.error(f"[RSS] Got HTML instead of XML from {url}: {content_preview}")
            return []
        
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            description = item.findtext("description", "").strip()
            if description:
                import re
                from html import unescape
                description = unescape(re.sub(r"<[^>]+>", " ", description))
                description = " ".join(description.split())
            pub_date = item.findtext("pubDate", "").strip()
            if title:
                items.append({"title": title, "description": description, "pubDate": pub_date})
        logger.info(f"[RSS] Parsed {len(items)} items from {url}")
        return items
    except requests.exceptions.Timeout:
        logger.error(f"[RSS] Request timeout for {url}")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"[RSS] HTTP error {e.response.status_code} for {url}: {e}")
        return []
    except Exception as e:
        logger.error(f"[RSS] Error parsing {url}: {type(e).__name__}: {e}")
        return []


def _parse_date_from_rfc2822(date_str: str):
    """Извлекает дату из строки RFC 2822."""
    from datetime import datetime
    import re
    cleaned = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*", "", date_str)
    for fmt in ["%d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S", "%d %B %Y %H:%M:%S %z", "%d %B %Y %H:%M:%S"]:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def get_yesterday_news():
    """
    Скачивает RSS Lenta.ru и Ysia.ru, фильтрует за вчера по якутскому времени.
    Берёт топ-8 федеральных и топ-3 якутских.
    
    ВАЖНО: используем Asia/Yakutsk (UTC+9), а не UTC, чтобы «вчера»
    соответствовало якутскому календарному дню.
    """
    import pytz
    from datetime import datetime, timedelta
    yakutsk_tz = pytz.timezone("Asia/Yakutsk")
    now_yakutsk = datetime.now(yakutsk_tz)
    yesterday = (now_yakutsk - timedelta(days=1)).date()

    lenta_items = _parse_rss_feed("https://lenta.ru/rss")
    federal_yesterday = []
    for item in lenta_items:
        pub_date = _parse_date_from_rfc2822(item["pubDate"])
        if pub_date == yesterday:
            federal_yesterday.append({
                "title": item["title"],
                "description": item["description"][:300] if item["description"] else "",
            })
            if len(federal_yesterday) >= 5:
                break

    ysia_items = _parse_rss_feed("https://ysia.ru/feed/")
    yakutia_yesterday = []
    for item in ysia_items:
        pub_date = _parse_date_from_rfc2822(item["pubDate"])
        if pub_date == yesterday:
            yakutia_yesterday.append({
                "title": item["title"],
                "description": item["description"][:300] if item["description"] else "",
            })
            if len(yakutia_yesterday) >= 5:
                break

    return {"federal": federal_yesterday, "yakutia": yakutia_yesterday}


def format_news_via_openai(news_data: dict):
    """Саммари новостей через Claude Haiku."""
    if not news_data or (not news_data.get("federal") and not news_data.get("yakutia")):
        return None

    federal_text = "\n".join(
        f"- {n['title']}: {n['description']}" for n in news_data.get("federal", [])
    ) if news_data.get("federal") else "(нет данных)"

    yakutia_text = "\n".join(
        f"- {n['title']}: {n['description']}" for n in news_data.get("yakutia", [])
    ) if news_data.get("yakutia") else "(нет данных)"

    system = (
        "Ты — новостной редактор. Делаешь короткие, информативные саммари. "
        "Без выдумок, только факты из запроса. Пиши по-русски. Количество знаков не менее 100 на каждую новость. сдлеай не менее 8 новостей В мире и России и 2-3 в Якутии"
    )
    user = f"""Вот новости за вчерашний день:

=== В МИРЕ И РОССИИ ===
{federal_text}

=== В ЯКУТИИ ===
{yakutia_text}

Сделай саммари вчерашних новостей.
Два блока: «В мире и России» и «В Якутии».
Коротко и по делу. Используй ТОЛЬКО текст из запроса.
Эмодзи — умеренно."""

    return _ai_call(system, user, max_tokens=1500)
