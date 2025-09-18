#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для мониторинга мест на поездах РЖД
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from rzd_parser import RZDParser
from database import Database
from monitoring import MonitoringService

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RZDBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.db = Database()
        self.parser = RZDParser()
        self.monitoring = MonitoringService(self.db, self.parser, token)
        
        # Состояния пользователей
        self.user_states = {}
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("my_subscriptions", self.my_subscriptions_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = (
            f"🚂 Добро пожаловать, {user.first_name}!\n\n"
            "Я помогу вам найти и отслеживать свободные места на поездах РЖД.\n\n"
            "Для начала работы введите станцию отправления:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои подписки", callback_data="my_subscriptions")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        
        # Устанавливаем состояние пользователя
        self.user_states[user.id] = {
            'state': 'waiting_departure',
            'data': {}
        }
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🚂 Помощь по использованию бота РЖД\n\n"
            "📝 Как пользоваться:\n"
            "1. Введите станцию отправления\n"
            "2. Введите станцию прибытия\n"
            "3. Выберите дату поездки\n"
            "4. Выберите поезд и тип места\n"
            "5. Бот начнет мониторинг и уведомит о свободных местах\n\n"
            "🔍 Команды:\n"
            "/start - начать работу\n"
            "/my_subscriptions - мои подписки\n"
            "/stats - статистика мониторинга\n"
            "/help - эта справка\n\n"
            "💡 Совет: Используйте полные названия станций для лучших результатов"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
    async def my_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /my_subscriptions"""
        user_id = update.effective_user.id
        subscriptions = await self.db.get_user_subscriptions(user_id)
        
        if not subscriptions:
            text = "📋 У вас пока нет активных подписок"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]]
        else:
            text = "📋 Ваши активные подписки:\n\n"
            keyboard = []
            
            for sub in subscriptions:
                text += (
                    f"🚂 {sub['train_number']} ({sub['departure_station']} → {sub['arrival_station']})\n"
                    f"📅 {sub['departure_date']}\n"
                    f"🛏️ {sub['seat_type']} ({sub['berth_position']})\n"
                    f"⏰ Создана: {sub['created_at']}\n\n"
                )
                keyboard.append([InlineKeyboardButton(
                    f"❌ Удалить {sub['train_number']}", 
                    callback_data=f"delete_sub_{sub['id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        try:
            stats = await self.monitoring.get_monitoring_stats()
            
            text = (
                "📊 Статистика мониторинга:\n\n"
                f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
                f"📋 Активных подписок: {stats.get('active_subscriptions', 0)}\n"
                f"🔔 Уведомлений за 24ч: {stats.get('notifications_24h', 0)}\n"
                f"🔄 Мониторинг работает: {'✅ Да' if stats.get('is_running', False) else '❌ Нет'}\n"
                f"⏰ Интервал проверки: {stats.get('check_interval', 0)} сек"
            )
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "back_to_start":
            await self.start_command(update, context)
        elif data == "help":
            await self.help_command(update, context)
        elif data == "my_subscriptions":
            await self.my_subscriptions_command(update, context)
        elif data.startswith("delete_sub_"):
            sub_id = int(data.split("_")[2])
            await self.db.delete_subscription(sub_id)
            await query.edit_message_text("✅ Подписка удалена")
        elif data.startswith("select_train_"):
            await self._handle_train_selection(query, data)
        elif data.startswith("select_seat_"):
            await self._handle_seat_selection(query, data)
        elif data.startswith("select_berth_"):
            await self._handle_berth_selection(query, data)
    
    async def _handle_train_selection(self, query, data):
        """Обработка выбора поезда"""
        train_data = data.replace("select_train_", "")
        train_info = train_data.split("|")
        
        user_id = query.from_user.id
        user_state = self.user_states.get(user_id, {})
        user_state['data']['selected_train'] = {
            'number': train_info[0],
            'departure_time': train_info[1],
            'arrival_time': train_info[2],
            'duration': train_info[3]
        }
        
        # Показываем типы мест
        keyboard = [
            [InlineKeyboardButton("🛏️ Плацкарт", callback_data="select_seat_плацкарт")],
            [InlineKeyboardButton("🚪 Купе", callback_data="select_seat_купе")],
            [InlineKeyboardButton("🏠 СВ", callback_data="select_seat_св")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚂 Выбран поезд {train_info[0]}\n"
            f"⏰ {train_info[1]} → {train_info[2]} ({train_info[3]})\n\n"
            "Выберите тип места:",
            reply_markup=reply_markup
        )
    
    async def _handle_seat_selection(self, query, data):
        """Обработка выбора типа места"""
        seat_type = data.replace("select_seat_", "")
        user_id = query.from_user.id
        user_state = self.user_states.get(user_id, {})
        user_state['data']['seat_type'] = seat_type
        
        if seat_type == "купе":
            # Для купе показываем выбор полки
            keyboard = [
                [InlineKeyboardButton("⬆️ Верхняя полка", callback_data="select_berth_верхняя")],
                [InlineKeyboardButton("⬇️ Нижняя полка", callback_data="select_berth_нижняя")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🛏️ Выбран тип места: {seat_type}\n\n"
                "Выберите полку:",
                reply_markup=reply_markup
            )
        else:
            # Для плацкарта и СВ сразу создаем подписку
            await self._create_subscription(query, seat_type, "любая")
    
    async def _handle_berth_selection(self, query, data):
        """Обработка выбора полки"""
        berth_position = data.replace("select_berth_", "")
        user_id = query.from_user.id
        user_state = self.user_states.get(user_id, {})
        seat_type = user_state['data'].get('seat_type', 'купе')
        
        await self._create_subscription(query, seat_type, berth_position)
    
    async def _create_subscription(self, query, seat_type, berth_position):
        """Создание подписки на мониторинг"""
        user_id = query.from_user.id
        user_state = self.user_states.get(user_id, {})
        user_data = user_state.get('data', {})
        
        # Получаем данные из состояния пользователя
        departure_station = user_data.get('departure_station')
        arrival_station = user_data.get('arrival_station')
        departure_date = user_data.get('departure_date')
        train_info = user_data.get('selected_train', {})
        
        if not all([departure_station, arrival_station, departure_date, train_info]):
            await query.edit_message_text("❌ Ошибка: не все данные заполнены")
            return
        
        # Создаем подписку в базе данных
        subscription_id = await self.db.create_subscription(
            user_id=user_id,
            departure_station=departure_station,
            arrival_station=arrival_station,
            departure_date=departure_date,
            train_number=train_info['number'],
            seat_type=seat_type,
            berth_position=berth_position
        )
        
        # Запускаем мониторинг для этой подписки
        await self.monitoring.start_monitoring(subscription_id)
        
        await query.edit_message_text(
            f"✅ Подписка создана!\n\n"
            f"🚂 Поезд: {train_info['number']}\n"
            f"📍 Маршрут: {departure_station} → {arrival_station}\n"
            f"📅 Дата: {departure_date}\n"
            f"🛏️ Место: {seat_type} ({berth_position})\n\n"
            "🔍 Мониторинг запущен! Я уведомлю вас, когда найду свободные места!\n\n"
            "💡 Для создания новой подписки используйте /start"
        )
        
        # Очищаем состояние пользователя
        self.user_states[user_id] = {'state': 'idle', 'data': {}}
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        user_state = self.user_states.get(user_id, {})
        current_state = user_state.get('state', 'idle')
        
        if current_state == 'waiting_departure':
            await self._handle_departure_station(update, text)
        elif current_state == 'waiting_arrival':
            await self._handle_arrival_station(update, text)
        elif current_state == 'waiting_date':
            await self._handle_date_selection(update, text)
        else:
            await update.message.reply_text(
                "Не понимаю команду. Используйте /start для начала работы."
            )
    
    async def _handle_departure_station(self, update: Update, text: str):
        """Обработка ввода станции отправления"""
        user_id = update.effective_user.id
        
        # Сохраняем станцию отправления
        self.user_states[user_id]['data']['departure_station'] = text
        self.user_states[user_id]['state'] = 'waiting_arrival'
        
        await update.message.reply_text(
            f"📍 Станция отправления: {text}\n\n"
            "Теперь введите станцию прибытия:"
        )
    
    async def _handle_arrival_station(self, update: Update, text: str):
        """Обработка ввода станции прибытия"""
        user_id = update.effective_user.id
        
        # Сохраняем станцию прибытия
        self.user_states[user_id]['data']['arrival_station'] = text
        self.user_states[user_id]['state'] = 'waiting_date'
        
        await update.message.reply_text(
            f"📍 Маршрут: {self.user_states[user_id]['data']['departure_station']} → {text}\n\n"
            "Введите дату поездки в формате ДД.ММ.ГГГГ (например, 15.12.2024):"
        )
    
    async def _handle_date_selection(self, update: Update, text: str):
        """Обработка выбора даты"""
        user_id = update.effective_user.id
        
        try:
            # Парсим дату
            departure_date = datetime.strptime(text, "%d.%m.%Y").strftime("%Y-%m-%d")
            
            # Проверяем, что дата не в прошлом
            if datetime.strptime(departure_date, "%Y-%m-%d") < datetime.now().date():
                await update.message.reply_text("❌ Дата не может быть в прошлом. Введите корректную дату:")
                return
            
            # Сохраняем дату
            self.user_states[user_id]['data']['departure_date'] = departure_date
            
            # Ищем поезда
            await self._search_trains(update, user_id)
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:"
            )
    
    async def _search_trains(self, update: Update, user_id: int):
        """Поиск поездов по маршруту и дате"""
        user_data = self.user_states[user_id]['data']
        
        await update.message.reply_text("🔍 Ищу поезда...")
        
        try:
            # Парсим данные с сайта РЖД
            trains = await self.parser.search_trains(
                departure_station=user_data['departure_station'],
                arrival_station=user_data['arrival_station'],
                departure_date=user_data['departure_date']
            )
            
            if not trains:
                await update.message.reply_text(
                    "❌ Поезда по данному маршруту не найдены. Попробуйте другой маршрут."
                )
                self.user_states[user_id] = {'state': 'idle', 'data': {}}
                return
            
            # Показываем найденные поезда
            text = f"🚂 Найдено поездов: {len(trains)}\n\n"
            keyboard = []
            
            for train in trains[:10]:  # Показываем максимум 10 поездов
                text += (
                    f"🚂 {train['number']}\n"
                    f"⏰ {train['departure_time']} → {train['arrival_time']}\n"
                    f"⏱️ В пути: {train['duration']}\n\n"
                )
                
                callback_data = f"select_train_{train['number']}|{train['departure_time']}|{train['arrival_time']}|{train['duration']}"
                keyboard.append([InlineKeyboardButton(
                    f"Выбрать {train['number']}", 
                    callback_data=callback_data
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Начать заново", callback_data="back_to_start")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка при поиске поездов: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске поездов. Попробуйте позже."
            )
            self.user_states[user_id] = {'state': 'idle', 'data': {}}
    
    async def run(self):
        """Запуск бота"""
        logger.info("Запуск бота РЖД...")
        
        try:
            # Инициализируем базу данных
            await self.db.initialize()
            logger.info("База данных инициализирована")
            
            # Запускаем мониторинг в фоне
            monitoring_task = asyncio.create_task(self.monitoring.run())
            logger.info("Мониторинг запущен")
            
            # Запускаем бота
            await self.application.run_polling()
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
        finally:
            # Останавливаем мониторинг
            if 'monitoring_task' in locals():
                await self.monitoring.stop()
                monitoring_task.cancel()
                try:
                    await monitoring_task
                except asyncio.CancelledError:
                    pass

async def main():
    """Главная функция"""
    # Получаем токен бота из переменной окружения
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("Не установлен TELEGRAM_BOT_TOKEN")
        return
    
    # Создаем и запускаем бота
    bot = RZDBot(bot_token)
    await bot.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

