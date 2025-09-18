#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример файла конфигурации
Скопируйте этот файл в config.py и заполните своими данными
"""

import os

# Токен Telegram бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'your_bot_token_here')

# Настройки мониторинга
MONITORING_INTERVAL = int(os.getenv('MONITORING_INTERVAL', '300'))  # 5 минут
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '60'))  # 1 минута

# Настройки базы данных
DATABASE_PATH = os.getenv('DATABASE_PATH', 'rzd_bot.db')

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Настройки парсера РЖД
RZD_BASE_URL = 'https://pass.rzd.ru'
REQUEST_TIMEOUT = 30  # Таймаут запросов в секундах
MAX_CONCURRENT_REQUESTS = 10  # Максимальное количество одновременных запросов

# Настройки уведомлений
NOTIFICATION_RETRY_COUNT = 3  # Количество попыток отправки уведомления
NOTIFICATION_RETRY_DELAY = 5   # Задержка между попытками в секундах

# Настройки очистки данных
CLEANUP_INTERVAL = 24 * 60 * 60  # Интервал очистки в секундах (24 часа)
DATA_RETENTION_DAYS = 30  # Количество дней хранения данных

