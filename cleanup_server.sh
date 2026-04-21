#!/bin/bash
# Скрипт для очистки сервера от старых версий бота перед деплоем
# Использование: bash cleanup_server.sh

set -e

echo "=========================================="
echo "Очистка сервера от старых версий бота"
echo "=========================================="
echo ""

# Определяем директорию бота
BOT_DIR="/opt/GoodMorning_bot"

# Проверяем, существует ли директория
if [ ! -d "$BOT_DIR" ]; then
    echo "Директория $BOT_DIR не найдена. Чистая установка."
    exit 0
fi

echo "Найдена старая версия бота в $BOT_DIR"
echo ""

# Останавливаем все процессы бота
echo "1. Остановка работающих процессов бота..."
pkill -f "python.*bot.py" 2>/dev/null || echo "   Нет активных процессов бота"
sleep 2

# Проверяем, что все процессы остановлены
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "   Принудительная остановка..."
    pkill -9 -f "python.*bot.py" 2>/dev/null || true
    sleep 1
fi
echo "   ✓ Все процессы бота остановлены"
echo ""

# Удаляем старую версию
echo "2. Удаление старой версии бота..."
rm -rf "$BOT_DIR"
echo "   ✓ Старая версия удалена"
echo ""

# Очищаем __pycache__ и временные файлы (если остались где-то)
echo "3. Очистка кэша Python..."
find /tmp -name "*GoodMorning*" -type d -exec rm -rf {} + 2>/dev/null || true
find /tmp -name "*.pyc" -delete 2>/dev/null || true
echo "   ✓ Кэш очищен"
echo ""

# Проверяем systemd service (если есть)
echo "4. Проверка systemd service..."
if systemctl is-active --quiet goodmorning-bot.service 2>/dev/null; then
    echo "   Остановка сервиса goodmorning-bot..."
    sudo systemctl stop goodmorning-bot.service
    sudo systemctl disable goodmorning-bot.service
    echo "   ✓ Сервис остановлен и отключён"
else
    echo "   Сервис goodmorning-bot не найден или уже остановлен"
fi
echo ""

echo "=========================================="
echo "✓ Очистка завершена успешно!"
echo "=========================================="
echo ""
echo "Теперь можно деплоить новую версию:"
echo "  cd /opt"
echo "  git clone <repository_url> GoodMorning_bot"
echo "  cd GoodMorning_bot"
echo "  pip install -r requirements.txt"
echo "  # Настроить .env файл"
echo "  # Запустить бота"
echo ""
