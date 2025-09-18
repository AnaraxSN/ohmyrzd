#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска бота РЖД
"""

import os
import sys
import asyncio
import logging
from main import RZDBot

def setup_logging():
    """Настройка логирования"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, log_level, logging.INFO),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('rzd_bot.log', encoding='utf-8')
        ]
    )

def check_requirements():
    """Проверка требований"""
    # Проверяем токен бота
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token or bot_token == 'your_bot_token_here':
        print("❌ Ошибка: Не установлен TELEGRAM_BOT_TOKEN")
        print("Установите переменную окружения:")
        print("export TELEGRAM_BOT_TOKEN='your_actual_bot_token'")
        return False
    
    # Проверяем наличие необходимых модулей
    try:
        import telegram
        import aiohttp
        import aiosqlite
        import bs4
    except ImportError as e:
        print(f"❌ Ошибка: Отсутствует необходимый модуль: {e}")
        print("Установите зависимости:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Главная функция"""
    print("🚂 Запуск бота РЖД...")
    
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Проверка требований
    if not check_requirements():
        sys.exit(1)
    
    try:
        # Получаем токен бота
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        print("✅ Бот запущен успешно!")
        print("Для остановки нажмите Ctrl+C")
        
        # Запускаем бота через asyncio.run
        asyncio.run(start_bot(bot_token))
        
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

async def start_bot(bot_token):
    """Асинхронная функция запуска бота"""
    logger = logging.getLogger(__name__)
    
    try:
        # Создаем и запускаем бота
        bot = RZDBot(bot_token)
        logger.info("Бот создан успешно")
        
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

