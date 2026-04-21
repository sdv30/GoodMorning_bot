# GoodMorning Bot ☀️

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-17%20passing-brightgreen.svg)](test_smoke.py)

Семейный Telegram-бот для автоматической рассылки утренних сообщений с погодой, красивыми фото, гороскопами и народным календарём.

## ✨ Возможности

- 🌤 **Прогноз погоды** - подробный прогноз на день из OpenWeatherMap
- 🖼 **Красивые фото** - случайные изображения природы из Unsplash
- ⭐ **Гороскопы** - персональный гороскоп с 1001goroskop.ru (знак зодиака настраивается)
- 📅 **Народный календарь** - праздники и приметы из Calend.ru
- 🤖 **AI-редактор** - умное форматирование через Claude Haiku
- ⏰ **Автоматическая рассылка** - сообщения по расписанию (07:30 и 08:00 Yakutsk)
- 💬 **Интерактивный режим** - ручная отправка команд через Telegram

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.8+
- Telegram Bot Token (получите у [@BotFather](https://t.me/BotFather))
- API ключи внешних сервисов

### Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/sdv30/GoodMorning_bot.git
cd GoodMorning_bot
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

3. Создайте файл `.env` на основе примера:
```bash
cp .env.example .env
```

4. Заполните `.env` своими API ключами:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
CHAT_ID=your_chat_id
AI_API_KEY=your_ai_api_key
OPENWEATHER_API_KEY=your_openweathermap_key
UNSPLASH_ACCESS_KEY=your_unsplash_key
```

5. Запустите бота:
```bash
python bot.py
```

## 📋 Команды

| Команда | Описание |
|---------|----------|
| `/morning` | Отправить утренний пост вручную |
| `/calendar` | Отправить народный календарь |
| `/help` | Показать справку |

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | Где получить |
|------------|----------|--------------|
| `TELEGRAM_TOKEN` | Токен Telegram бота | [@BotFather](https://t.me/BotFather) |
| `CHAT_ID` | ID чата для рассылки | [@userinfobot](https://t.me/userinfobot) |
| `AI_API_KEY` | Ключ AI API | Ваш поставщик ИИ |
| `OPENWEATHER_API_KEY` | Ключ Weather API | [openweathermap.org](https://openweathermap.org/api) |
| `UNSPLASH_ACCESS_KEY` | Ключ Unsplash API | [unsplash.com/developers](https://unsplash.com/developers) |

### Расписание

Бот автоматически отправляет сообщения по якутскому времени (UTC+9):

- **07:30** - Утренний пост (погода, фото, гороскоп, пожелание)
- **08:00** - Народный календарь (праздники, приметы, советы)

## 🧪 Тестирование

Запуск unit-тестов:
```bash
python test_smoke.py -v
```

Health check:
```bash
python bot.py health
```

## 🖥 Деплой на сервер

### Автоматический деплой (Linux/systemd)

```bash
sudo bash deploy.sh --install-dir /opt/GoodMorning_bot --service-name goodmorning-bot
```

### Ручной деплой

1. Скопируйте файлы на сервер:
```bash
scp -r ./* user@server:/opt/GoodMorning_bot/
```

2. Настройте systemd service (см. `deploy.sh`)

3. Запустите сервис:
```bash
sudo systemctl start goodmorning-bot
sudo systemctl enable goodmorning-bot
```

Подробнее см. [DEPLOY_INSTRUCTIONS.md](DEPLOY_INSTRUCTIONS.md)

## 📁 Структура проекта

```
GoodMorning_bot/
├── bot.py              # Основная логика бота
├── services.py         # Внешние API сервисы
├── config.py           # Конфигурация и валидация
├── test_smoke.py       # Unit-тесты
├── requirements.txt    # Python зависимости
├── deploy.sh           # Скрипт деплоя
├── cleanup_server.sh   # Скрипт очистки сервера
├── .env.example        # Пример файла окружения
└── .gitignore          # Git ignore rules
```

## 🔧 Технологии

- **Telegram Bot API** - взаимодействие с Telegram
- **OpenWeatherMap** - прогноз погоды
- **Unsplash API** - красивые фотографии
- **1001goroskop.ru** - парсинг гороскопов (HTML scraping)
- **Calend.ru RSS** - народные праздники и приметы
- **AI API** - AI-редактор текста (ваш поставщик ИИ)
- **pytz** - работа с часовыми поясами
- **systemd** - управление сервисом на Linux

## 📊 Источники данных

| Данные | Источник | Метод получения |
|--------|----------|-----------------|
| 🌤 Погода | [OpenWeatherMap](https://openweathermap.org/) | REST API (forecast) |
| 🖼 Фото | [Unsplash](https://unsplash.com/) | REST API (random photos) |
| ⭐ Гороскопы | [1001goroskop.ru](https://1001goroskop.ru/) | HTML парсинг (знак: aries/Овен) |
| 📅 Календарь | [Calend.ru](https://calend.ru/) | RSS feed |
| 🤖 AI текст | Ваш поставщик ИИ | API (настраивается в .env) |

### Настройка знака зодиака

По умолчанию бот использует знак **Овен (aries)** для гороскопов. Чтобы изменить:

1. Откройте `bot.py`
2. Найдите строку:
   ```python
   ignio_raw = get_ignio_astrology("aries")
   ```
3. Замените `"aries"` на нужный знак:
   - `"taurus"` - Телец
   - `"gemini"` - Близнецы  
   - `"cancer"` - Рак
   - `"leo"` - Лев
   - `"virgo"` - Дева
   - `"libra"` - Весы
   - `"scorpio"` - Скорпион
   - `"sagittarius"` - Стрелец
   - `"capricorn"` - Козерог
   - `"aquarius"` - Водолей
   - `"pisces"` - Рыбы

### ⏰ Настройка часового пояса

По умолчанию бот работает по **якутскому времени (Asia/Yakutsk, UTC+9)**. Если ваш город в другом часовом поясе:

1. Откройте `bot.py`
2. Найдите все occurrences `Asia/Yakutsk` и замените на ваш часовой пояс:
   ```python
   # Было
   yakutsk_tz = pytz.timezone("Asia/Yakutsk")
   
   # Стало (например, для Москвы)
   yakutsk_tz = pytz.timezone("Europe/Moscow")
   
   # Или для Владивостока
   yakutsk_tz = pytz.timezone("Asia/Vladivostok")
   
   # Или для Нью-Йорка
   yakutsk_tz = pytz.timezone("America/New_York")
   ```

3. Измените расписание в функции `polling_loop()`:
   ```python
   TASK_SCHEDULE = [
       (7, 30, "morning", run_morning),   # 07:30 - утренний пост
       (8, 0, "calendar", run_calendar),  # 08:00 - народный календарь
   ]
   ```
   Укажите нужное время в вашем часовом поясе.

4. Обновите координаты для погоды в `.env`:
   ```env
   YAKUTSK_LAT=55.7558    # Широта вашего города
   YAKUTSK_LON=37.6173    # Долгота вашего города
   ```

**Популярные часовые пояса:**
- `Europe/Moscow` - Москва (UTC+3)
- `Asia/Yekaterinburg` - Екатеринбург (UTC+5)
- `Asia/Novosibirsk` - Новосибирск (UTC+7)
- `Asia/Vladivostok` - Владивосток (UTC+10)
- `Asia/Magadan` - Магадан (UTC+11)
- `America/New_York` - Нью-Йорк (UTC-5/-4)
- `America/Los_Angeles` - Лос-Анджелес (UTC-8/-7)

Полный список: [список часовых поясов IANA](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

## 🛡 Безопасность

⚠️ **Никогда не коммитьте файл `.env`!** Он содержит чувствительные данные.

Файл `.gitignore` настроен на исключение:
- `.env` - переменные окружения с API ключами
- `logs/` - логи приложения
- `__pycache__/` - кэш Python
- `.last_update_id` - runtime данные

## 🐛 Решение проблем

### Бот не запускается
```bash
# Проверьте health
python bot.py health

# Посмотрите логи
tail -f logs/bot.log
```

### Ошибка 409 Conflict
Другой экземпляр бота уже запущен с этим токеном. Найдите и остановите все процессы:
```bash
pkill -f "python.*bot.py"
```

### Планировщик не срабатывает
Проверьте часовой пояс сервера и логи:
```bash
grep SCHEDULER logs/bot.log
```

Подробнее см. [DEPLOY_INSTRUCTIONS.md](DEPLOY_INSTRUCTIONS.md)

## 📝 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## 👤 Автор

**sdv30**

- GitHub: [@sdv30](https://github.com/sdv30)

## 🙏 Благодарности

- [OpenWeatherMap](https://openweathermap.org/) за API погоды
- [Unsplash](https://unsplash.com/) за красивые фотографии
- [Calend.ru](https://calend.ru/) за народный календарь
- [Claude AI](https://www.anthropic.com/claude) за умное форматирование текста

---

⭐ Если вам понравился этот проект, поставьте звёздочку на GitHub!
