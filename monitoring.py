#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль мониторинга доступности мест
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from telegram import Bot
from telegram.error import TelegramError

from database import Database
from rzd_parser import RZDParser

logger = logging.getLogger(__name__)

class MonitoringService:
    """Сервис мониторинга доступности мест"""
    
    def __init__(self, db: Database, parser: RZDParser, bot_token: str = None):
        self.db = db
        self.parser = parser
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token) if bot_token else None
        self.is_running = False
        self.check_interval = 300  # 5 минут
        self.max_retries = 3
        self.retry_delay = 60  # 1 минута
    
    async def run(self):
        """Запуск сервиса мониторинга"""
        self.is_running = True
        logger.info("Сервис мониторинга запущен")
        
        # Ждем инициализации базы данных
        while not self.db._initialized:
            await asyncio.sleep(1)
        
        # Небольшая задержка для стабильности
        await asyncio.sleep(5)
        
        while self.is_running:
            try:
                await self._check_all_subscriptions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Ошибка в сервисе мониторинга: {e}")
                await asyncio.sleep(self.retry_delay)
    
    async def stop(self):
        """Остановка сервиса мониторинга"""
        self.is_running = False
        logger.info("Сервис мониторинга остановлен")
    
    async def start_monitoring(self, subscription_id: int):
        """
        Запуск мониторинга для конкретной подписки
        
        Args:
            subscription_id: ID подписки
        """
        logger.info(f"Запуск мониторинга для подписки {subscription_id}")
        
        # Проверяем подписку сразу
        await self._check_subscription(subscription_id)
    
    async def _check_all_subscriptions(self):
        """Проверка всех активных подписок"""
        try:
            subscriptions = await self.db.get_active_subscriptions()
            logger.info(f"Проверка {len(subscriptions)} активных подписок")
            
            # Создаем задачи для параллельной проверки
            tasks = []
            for subscription in subscriptions:
                task = asyncio.create_task(
                    self._check_subscription(subscription['id'])
                )
                tasks.append(task)
            
            # Ждем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке всех подписок: {e}")
    
    async def _check_subscription(self, subscription_id: int):
        """
        Проверка конкретной подписки
        
        Args:
            subscription_id: ID подписки
        """
        try:
            # Получаем информацию о подписке
            subscriptions = await self.db.get_active_subscriptions()
            subscription = next(
                (s for s in subscriptions if s['id'] == subscription_id), 
                None
            )
            
            if not subscription:
                logger.warning(f"Подписка {subscription_id} не найдена")
                return
            
            # Проверяем доступность мест
            availability_info = await self.parser.check_seat_availability(
                train_number=subscription['train_number'],
                departure_station=subscription['departure_station'],
                arrival_station=subscription['arrival_station'],
                departure_date=subscription['departure_date'],
                seat_type=subscription['seat_type'],
                berth_position=subscription['berth_position']
            )
            
            # Обновляем время последней проверки
            await self.db.update_last_checked(subscription_id)
            
            # Добавляем запись в историю проверок
            seats_info = str(availability_info) if availability_info else None
            await self.db.add_check_history(
                subscription_id, 
                availability_info.get('available', False),
                seats_info
            )
            
            # Если места доступны, отправляем уведомление
            if availability_info.get('available', False):
                await self._send_notification(subscription, availability_info)
            
            logger.info(f"Проверка подписки {subscription_id} завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки {subscription_id}: {e}")
    
    async def _send_notification(self, subscription: Dict, availability_info: Dict):
        """
        Отправка уведомления о найденных местах
        
        Args:
            subscription: Информация о подписке
            availability_info: Информация о доступности мест
        """
        try:
            if not self.bot:
                logger.warning("Бот не настроен для отправки уведомлений")
                return
            
            # Формируем сообщение
            message = self._format_notification_message(subscription, availability_info)
            
            # Отправляем уведомление
            await self.bot.send_message(
                chat_id=subscription['telegram_id'],
                text=message,
                parse_mode='HTML'
            )
            
            # Сохраняем уведомление в базу данных
            await self.db.add_notification(subscription['id'], message)
            
            logger.info(f"Уведомление отправлено пользователю {subscription['telegram_id']}")
            
        except TelegramError as e:
            logger.error(f"Ошибка Telegram при отправке уведомления: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
    
    def _format_notification_message(self, subscription: Dict, availability_info: Dict) -> str:
        """
        Форматирование сообщения уведомления
        
        Args:
            subscription: Информация о подписке
            availability_info: Информация о доступности мест
            
        Returns:
            Отформатированное сообщение
        """
        message = (
            f"🎉 <b>Найдены свободные места!</b>\n\n"
            f"🚂 <b>Поезд:</b> {subscription['train_number']}\n"
            f"📍 <b>Маршрут:</b> {subscription['departure_station']} → {subscription['arrival_station']}\n"
            f"📅 <b>Дата:</b> {subscription['departure_date']}\n"
            f"🛏️ <b>Тип места:</b> {subscription['seat_type']}\n"
        )
        
        if subscription['berth_position'] != 'любая':
            message += f"🛏️ <b>Полка:</b> {subscription['berth_position']}\n"
        
        # Добавляем информацию о найденных местах
        if availability_info.get('price'):
            message += f"💰 <b>Цена:</b> {availability_info['price']}\n"
        
        if availability_info.get('car_number'):
            message += f"🚃 <b>Вагон:</b> {availability_info['car_number']}\n"
        
        if availability_info.get('seat_number'):
            message += f"🪑 <b>Место:</b> {availability_info['seat_number']}\n"
        
        message += (
            f"\n⏰ <b>Время уведомления:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Ссылка для бронирования:</b>\n"
            f"https://pass.rzd.ru/tickets/public/ru"
        )
        
        return message
    
    async def get_monitoring_stats(self) -> Dict:
        """
        Получение статистики мониторинга
        
        Returns:
            Словарь со статистикой
        """
        try:
            stats = await self.db.get_statistics()
            stats['is_running'] = self.is_running
            stats['check_interval'] = self.check_interval
            return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики мониторинга: {e}")
            return {}
    
    async def update_check_interval(self, interval: int):
        """
        Обновление интервала проверки
        
        Args:
            interval: Новый интервал в секундах
        """
        if interval < 60:  # Минимум 1 минута
            interval = 60
        
        self.check_interval = interval
        logger.info(f"Интервал проверки обновлен: {interval} секунд")
    
    async def cleanup_old_subscriptions(self):
        """Очистка старых подписок"""
        try:
            # Деактивируем подписки на прошедшие даты
            subscriptions = await self.db.get_active_subscriptions()
            deactivated_count = 0
            
            for subscription in subscriptions:
                departure_date = datetime.strptime(subscription['departure_date'], '%Y-%m-%d').date()
                if departure_date < datetime.now().date():
                    await self.db.deactivate_subscription(subscription['id'])
                    deactivated_count += 1
            
            if deactivated_count > 0:
                logger.info(f"Деактивировано {deactivated_count} подписок на прошедшие даты")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых подписок: {e}")
    
    async def test_notification(self, telegram_id: int):
        """
        Тестовая отправка уведомления
        
        Args:
            telegram_id: ID пользователя в Telegram
        """
        try:
            if not self.bot:
                logger.warning("Бот не настроен для отправки уведомлений")
                return False
            
            test_message = (
                "🧪 <b>Тестовое уведомление</b>\n\n"
                "Это тестовое сообщение для проверки работы системы уведомлений.\n"
                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=test_message,
                parse_mode='HTML'
            )
            
            logger.info(f"Тестовое уведомление отправлено пользователю {telegram_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке тестового уведомления: {e}")
            return False

