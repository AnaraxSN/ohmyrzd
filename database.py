#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import aiosqlite

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных SQLite"""
    
    def __init__(self, db_path: str = "rzd_bot.db"):
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Асинхронная инициализация базы данных"""
        if self._initialized:
            return
        
        try:
            # Создаем директорию для базы данных если не существует
            import os
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            # Создаем таблицы асинхронно
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                # Таблица пользователей
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица подписок на мониторинг
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        departure_station TEXT NOT NULL,
                        arrival_station TEXT NOT NULL,
                        departure_date DATE NOT NULL,
                        train_number TEXT NOT NULL,
                        seat_type TEXT NOT NULL,
                        berth_position TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_checked TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                    )
                ''')
                
                # Таблица уведомлений
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subscription_id INTEGER NOT NULL,
                        message TEXT NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                    )
                ''')
                
                # Таблица истории проверок
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS check_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subscription_id INTEGER NOT NULL,
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        seats_available BOOLEAN DEFAULT 0,
                        seats_info TEXT,
                        FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                    )
                ''')
                
                await db.commit()
            
            self._initialized = True
            logger.info("База данных инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    async def _get_connection(self):
        """Получение соединения с базой данных"""
        return aiosqlite.connect(self.db_path)
    
    def _init_db(self):
        """Инициализация базы данных"""
        try:
            # Создаем директорию для базы данных если не существует
            import os
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            # Создаем таблицы синхронно
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица подписок на мониторинг
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    departure_station TEXT NOT NULL,
                    arrival_station TEXT NOT NULL,
                    departure_date DATE NOT NULL,
                    train_number TEXT NOT NULL,
                    seat_type TEXT NOT NULL,
                    berth_position TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Таблица уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                )
            ''')
            
            # Таблица истории проверок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS check_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    seats_available BOOLEAN DEFAULT 0,
                    seats_info TEXT,
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("База данных инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    async def add_user(self, telegram_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None) -> bool:
        """
        Добавление пользователя в базу данных
        
        Args:
            telegram_id: ID пользователя в Telegram
            username: Имя пользователя
            first_name: Имя
            last_name: Фамилия
            
        Returns:
            True если пользователь добавлен, False если уже существует
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                # Проверяем, существует ли пользователь
                await cursor.execute(
                    "SELECT id FROM users WHERE telegram_id = ?", 
                    (telegram_id,)
                )
                existing_user = await cursor.fetchone()
                
                if existing_user:
                    return False
                
                # Добавляем пользователя
                await cursor.execute('''
                    INSERT INTO users (telegram_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                ''', (telegram_id, username, first_name, last_name))
                
                await db.commit()
                logger.info(f"Пользователь {telegram_id} добавлен в базу данных")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя: {e}")
            return False
    
    async def create_subscription(self, user_id: int, departure_station: str,
                                arrival_station: str, departure_date: str,
                                train_number: str, seat_type: str,
                                berth_position: str) -> int:
        """
        Создание подписки на мониторинг
        
        Args:
            user_id: ID пользователя
            departure_station: Станция отправления
            arrival_station: Станция прибытия
            departure_date: Дата отправления
            train_number: Номер поезда
            seat_type: Тип места
            berth_position: Позиция полки
            
        Returns:
            ID созданной подписки
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                # Проверяем, существует ли уже такая подписка
                await cursor.execute('''
                    SELECT id FROM subscriptions 
                    WHERE user_id = ? AND departure_station = ? AND arrival_station = ?
                    AND departure_date = ? AND train_number = ? AND seat_type = ?
                    AND berth_position = ? AND is_active = 1
                ''', (user_id, departure_station, arrival_station, departure_date,
                     train_number, seat_type, berth_position))
                
                existing_sub = await cursor.fetchone()
                if existing_sub:
                    return existing_sub[0]
                
                # Создаем новую подписку
                await cursor.execute('''
                    INSERT INTO subscriptions 
                    (user_id, departure_station, arrival_station, departure_date,
                     train_number, seat_type, berth_position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, departure_station, arrival_station, departure_date,
                     train_number, seat_type, berth_position))
                
                subscription_id = cursor.lastrowid
                await db.commit()
                
                logger.info(f"Создана подписка {subscription_id} для пользователя {user_id}")
                return subscription_id
                
        except Exception as e:
            logger.error(f"Ошибка при создании подписки: {e}")
            raise
    
    async def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """
        Получение подписок пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список подписок
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.cursor()
                
                await cursor.execute('''
                    SELECT * FROM subscriptions 
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                rows = await cursor.fetchall()
                subscriptions = []
                
                for row in rows:
                    subscriptions.append({
                        'id': row['id'],
                        'departure_station': row['departure_station'],
                        'arrival_station': row['arrival_station'],
                        'departure_date': row['departure_date'],
                        'train_number': row['train_number'],
                        'seat_type': row['seat_type'],
                        'berth_position': row['berth_position'],
                        'created_at': row['created_at'],
                        'last_checked': row['last_checked']
                    })
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"Ошибка при получении подписок пользователя: {e}")
            return []
    
    async def get_active_subscriptions(self) -> List[Dict]:
        """
        Получение всех активных подписок
        
        Returns:
            Список активных подписок
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.cursor()
                
                await cursor.execute('''
                    SELECT s.*, u.telegram_id, u.first_name 
                    FROM subscriptions s
                    JOIN users u ON s.user_id = u.telegram_id
                    WHERE s.is_active = 1
                    ORDER BY s.created_at DESC
                ''')
                
                rows = await cursor.fetchall()
                subscriptions = []
                
                for row in rows:
                    subscriptions.append({
                        'id': row['id'],
                        'user_id': row['user_id'],
                        'telegram_id': row['telegram_id'],
                        'first_name': row['first_name'],
                        'departure_station': row['departure_station'],
                        'arrival_station': row['arrival_station'],
                        'departure_date': row['departure_date'],
                        'train_number': row['train_number'],
                        'seat_type': row['seat_type'],
                        'berth_position': row['berth_position'],
                        'created_at': row['created_at'],
                        'last_checked': row['last_checked']
                    })
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"Ошибка при получении активных подписок: {e}")
            return []
    
    async def update_last_checked(self, subscription_id: int) -> bool:
        """
        Обновление времени последней проверки
        
        Args:
            subscription_id: ID подписки
            
        Returns:
            True если обновление прошло успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                await cursor.execute('''
                    UPDATE subscriptions 
                    SET last_checked = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (subscription_id,))
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении времени проверки: {e}")
            return False
    
    async def add_check_history(self, subscription_id: int, seats_available: bool,
                              seats_info: str = None) -> bool:
        """
        Добавление записи в историю проверок
        
        Args:
            subscription_id: ID подписки
            seats_available: Доступны ли места
            seats_info: Информация о местах
            
        Returns:
            True если запись добавлена
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                await cursor.execute('''
                    INSERT INTO check_history (subscription_id, seats_available, seats_info)
                    VALUES (?, ?, ?)
                ''', (subscription_id, seats_available, seats_info))
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении записи в историю: {e}")
            return False
    
    async def add_notification(self, subscription_id: int, message: str) -> bool:
        """
        Добавление уведомления
        
        Args:
            subscription_id: ID подписки
            message: Текст уведомления
            
        Returns:
            True если уведомление добавлено
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                await cursor.execute('''
                    INSERT INTO notifications (subscription_id, message)
                    VALUES (?, ?)
                ''', (subscription_id, message))
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении уведомления: {e}")
            return False
    
    async def deactivate_subscription(self, subscription_id: int) -> bool:
        """
        Деактивация подписки
        
        Args:
            subscription_id: ID подписки
            
        Returns:
            True если подписка деактивирована
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                await cursor.execute('''
                    UPDATE subscriptions 
                    SET is_active = 0
                    WHERE id = ?
                ''', (subscription_id,))
                
                await db.commit()
                logger.info(f"Подписка {subscription_id} деактивирована")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при деактивации подписки: {e}")
            return False
    
    async def delete_subscription(self, subscription_id: int) -> bool:
        """
        Удаление подписки
        
        Args:
            subscription_id: ID подписки
            
        Returns:
            True если подписка удалена
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                await cursor.execute('DELETE FROM subscriptions WHERE id = ?', (subscription_id,))
                await db.commit()
                
                logger.info(f"Подписка {subscription_id} удалена")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при удалении подписки: {e}")
            return False
    
    async def cleanup_old_data(self, days: int = 30) -> bool:
        """
        Очистка старых данных
        
        Args:
            days: Количество дней для хранения данных
            
        Returns:
            True если очистка прошла успешно
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                # Удаляем старые записи истории проверок
                await cursor.execute('''
                    DELETE FROM check_history 
                    WHERE checked_at < datetime('now', '-{} days')
                '''.format(days))
                
                # Удаляем старые уведомления
                await cursor.execute('''
                    DELETE FROM notifications 
                    WHERE sent_at < datetime('now', '-{} days')
                '''.format(days))
                
                # Деактивируем подписки на прошедшие даты
                await cursor.execute('''
                    UPDATE subscriptions 
                    SET is_active = 0
                    WHERE departure_date < date('now')
                ''')
                
                await db.commit()
                logger.info(f"Очистка данных старше {days} дней выполнена")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при очистке данных: {e}")
            return False
    
    async def get_statistics(self) -> Dict:
        """
        Получение статистики
        
        Returns:
            Словарь со статистикой
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                
                # Общее количество пользователей
                await cursor.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]
                
                # Активные подписки
                await cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active = 1")
                active_subscriptions = (await cursor.fetchone())[0]
                
                # Уведомления за последние 24 часа
                await cursor.execute('''
                    SELECT COUNT(*) FROM notifications 
                    WHERE sent_at > datetime('now', '-1 day')
                ''')
                notifications_24h = (await cursor.fetchone())[0]
                
                return {
                    'total_users': total_users,
                    'active_subscriptions': active_subscriptions,
                    'notifications_24h': notifications_24h
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {}

