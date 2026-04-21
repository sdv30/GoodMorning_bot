#!/usr/bin/env bash
###############################################################################
# deploy.sh — деплой ТЕКУЩЕГО репозитория на Ubuntu/systemd
#
# Важно: скрипт копирует bot.py/services.py/config.py и прочие файлы из текущей
# папки, а не генерирует их внутри deploy.sh. Это исключает рассинхрон кода.
#
# Запуск:
#   sudo bash deploy.sh
#   sudo bash deploy.sh --install-dir /root/G8dMorning_bot --service-name g8dmorning
###############################################################################

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

INSTALL_DIR="/root/G8dMorning_bot"
SERVICE_NAME="g8dmorning"
PYTHON_BIN="/usr/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --service-name) SERVICE_NAME="$2"; shift 2 ;;
        --python-bin) PYTHON_BIN="$2"; shift 2 ;;
        --help)
            echo "Использование:"
            echo "  sudo bash deploy.sh [--install-dir /root/G8dMorning_bot] [--service-name g8dmorning]"
            echo "                     [--python-bin /usr/bin/python3]"
            exit 0
            ;;
        *) log_error "Неизвестный аргумент: $1"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    log_error "Скрипт нужно запускать с правами root (sudo)."
    exit 1
fi

for required in bot.py services.py config.py requirements.txt; do
    if [[ ! -f "$SCRIPT_DIR/$required" ]]; then
        log_error "Не найден обязательный файл: $SCRIPT_DIR/$required"
        exit 1
    fi
done

log_info "Шаг 1: Установка системных пакетов..."
apt update -y
apt install -y python3 python3-pip python3-venv

log_info "Шаг 2: Очистка старой версии бота..."
# Останавливаем старый бот перед деплоем
if pgrep -f "python.*bot.py" > /dev/null; then
    log_warn "Обнаружен работающий бот, остановка..."
    pkill -f "python.*bot.py" || true
    sleep 2
    # Принудительная остановка если не остановился
    if pgrep -f "python.*bot.py" > /dev/null; then
        pkill -9 -f "python.*bot.py" || true
        sleep 1
    fi
    log_info "✓ Старый бот остановлен"
else
    log_info "Работающий бот не обнаружен"
fi

# Очищаем __pycache__
find "$INSTALL_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR" -name "*.pyc" -delete 2>/dev/null || true
log_info "✓ Кэш Python очищен"

log_info "Шаг 3: Подготовка директории деплоя..."
mkdir -p "$INSTALL_DIR"

log_info "Шаг 4: Копирование текущего кода..."
cp "$SCRIPT_DIR/bot.py" "$INSTALL_DIR/bot.py"
cp "$SCRIPT_DIR/services.py" "$INSTALL_DIR/services.py"
cp "$SCRIPT_DIR/config.py" "$INSTALL_DIR/config.py"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"

if [[ -f "$SCRIPT_DIR/test_smoke.py" ]]; then
    cp "$SCRIPT_DIR/test_smoke.py" "$INSTALL_DIR/test_smoke.py"
fi
if [[ -f "$SCRIPT_DIR/.env.example" ]]; then
    cp "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env.example"
fi

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        cp "$SCRIPT_DIR/.env" "$INSTALL_DIR/.env"
        chmod 600 "$INSTALL_DIR/.env"
        log_info "Скопирован .env из репозитория (только первый раз)"
    else
        log_warn ".env не найден ни в $INSTALL_DIR, ни в репозитории. Создайте его вручную."
    fi
fi

log_info "Шаг 5: Виртуальное окружение и зависимости..."
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    "$PYTHON_BIN" -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

log_info "Шаг 6: Настройка systemd..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=GoodMorning Family Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

log_info "Шаг 7: Post-deploy проверки..."
cd "$INSTALL_DIR"

if "$INSTALL_DIR/venv/bin/python" bot.py health; then
    log_info "Health-check пройден"
else
    log_error "Health-check не пройден"
    exit 1
fi

if [[ -f "$INSTALL_DIR/test_smoke.py" ]]; then
    if "$INSTALL_DIR/venv/bin/python" -m unittest test_smoke.py; then
        log_info "Smoke-тесты пройдены"
    else
        log_error "Smoke-тесты не пройдены"
        exit 1
    fi
else
    log_warn "test_smoke.py не найден, smoke-тесты пропущены"
fi

echo
log_info "============================================"
log_info "✅ Деплой завершён"
log_info "============================================"
log_info "Папка: $INSTALL_DIR"
log_info "Сервис: $SERVICE_NAME"
log_info "Проверка статуса: systemctl status $SERVICE_NAME"
log_info "Логи: journalctl -u $SERVICE_NAME -f"
