import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import requests

# Устанавливаем тестовые переменные окружения ПЕРЕД импортом модулей
os.environ['TELEGRAM_TOKEN'] = 'test_token'
os.environ['CHAT_ID'] = '123'
os.environ['AI_API_KEY'] = 'test_key'
os.environ['OPENWEATHER_API_KEY'] = 'test_weather_key'
os.environ['UNSPLASH_ACCESS_KEY'] = 'test_unsplash_key'

import bot
import services


class SmokeTests(unittest.TestCase):
    def test_get_date_string_returns_text(self):
        value = bot.get_date_string()
        self.assertIsInstance(value, str)
        self.assertGreater(len(value), 5)

    def test_health_check_ok_with_valid_minimum_config(self):
        with patch.object(bot, "TELEGRAM_TOKEN", "token"), patch.object(bot, "CHAT_ID", "123"), patch.object(
            bot, "TG_API", "https://api.telegram.org/bottoken"
        ):
            self.assertEqual(bot.run_health_check(), 0)

    def test_health_check_fails_on_invalid_tg_api(self):
        with patch.object(bot, "TELEGRAM_TOKEN", "token"), patch.object(bot, "CHAT_ID", "123"), patch.object(
            bot, "TG_API", "http://bad-url"
        ):
            self.assertEqual(bot.run_health_check(), 1)

    def test_astrology_formatter_wraps_text(self):
        raw = "Сегодня хороший день для спокойных решений."
        text = services.format_astrology_via_openai(raw)
        self.assertIsInstance(text, str)
        self.assertIn("Гороскоп для Людмилы", text)
        self.assertIn(raw, text)

    def test_astrology_formatter_none(self):
        self.assertIsNone(services.format_astrology_via_openai(None))


class ServiceFailureTests(unittest.TestCase):
    """Тесты для обработки сбоев внешних сервисов"""
    
    @patch('services.session.get')
    def test_weather_api_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        result = services.get_weather_forecast()
        self.assertIsNone(result)
    
    @patch('services.session.get')
    def test_weather_api_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = requests.exceptions.HTTPError()
        error.response = mock_response
        mock_response.raise_for_status.side_effect = error
        mock_get.return_value = mock_response
        
        result = services.get_weather_forecast()
        self.assertIsNone(result)
    
    @patch('services.session.get')
    def test_unsplash_api_failure(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        result = services.get_random_image_url()
        # Должен вернуть fallback URL
        self.assertEqual(result, "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1200")
    
    @patch('services.session.get')
    def test_calend_html_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body>Error</body></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = services.get_calend_holidays()
        self.assertEqual(result, [])
    
    @patch('services.session.get')
    def test_goroskop_cloudflare_protection(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.headers = {"cf-ray": "some-value"}
        mock_get.return_value = mock_response
        
        result = services.get_ignio_astrology("aries")
        self.assertIsNone(result)


class BotLogicTests(unittest.TestCase):
    """Тесты логики бота"""
    
    def test_send_long_message_splits_correctly(self):
        long_text = "A" * 8000
        with patch('bot.tg_send_message') as mock_send:
            bot.tg_send_long_message("123", long_text)
            # 8000 / 3800 = 3 chunk'а (3800 + 3800 + 400)
            self.assertEqual(mock_send.call_count, 3)
    
    def test_send_long_message_empty(self):
        with patch('bot.tg_send_message') as mock_send:
            bot.tg_send_long_message("123", "")
            mock_send.assert_not_called()
    
    def test_handle_morning_command(self):
        with patch('bot.tg_send_message') as mock_send, \
             patch('bot.run_morning') as mock_run:
            bot.handle_message({
                "text": "/morning", 
                "chat": {"id": "123", "type": "private"}
            })
            mock_send.assert_called_once()
            mock_run.assert_called_once()
    
    def test_handle_unknown_command(self):
        with patch('bot.tg_send_message') as mock_send:
            bot.handle_message({
                "text": "/unknown", 
                "chat": {"id": "123", "type": "private"}
            })
            mock_send.assert_called_once()
            self.assertIn("Unknown command", mock_send.call_args[1]['text'])
    
    def test_handle_message_wrong_chat(self):
        with patch('bot.tg_send_message') as mock_send:
            # Сообщение из чужого чата должно игнорироваться
            bot.handle_message({
                "text": "/morning", 
                "chat": {"id": "999", "type": "group"}
            })
            mock_send.assert_not_called()


class TimezoneTests(unittest.TestCase):
    """Тесты работы с часовыми поясами"""
    
    def test_get_yakutsk_now_returns_tz_aware_datetime(self):
        now = bot.get_yakutsk_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(str(now.tzinfo), "Asia/Yakutsk")
    
    def test_get_date_string_format(self):
        date_str = bot.get_date_string()
        # Проверяем формат: DD.MM.YYYY, <день недели>
        self.assertRegex(date_str, r'\d{2}\.\d{2}\.\d{4}, .+')


if __name__ == "__main__":
    unittest.main()
