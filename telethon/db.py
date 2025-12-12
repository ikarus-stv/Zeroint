"""
Модуль для работы с локальной базой данных SQLite.

Содержит функции для создания таблиц и сохранения сообщений.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_name: str = "telegram_messages.db"):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_name: Имя файла базы данных
        """
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Создает и возвращает подключение к базе данных.
        
        Returns:
            sqlite3.Connection: Подключение к базе данных
        """
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Создает таблицу messages, если она не существует."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    sender TEXT,
                    text TEXT,
                    date TIMESTAMP,
                    UNIQUE(id, chat_id)
                )
            """)
            
            # Создаем индексы для быстрого поиска
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_id ON messages(chat_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date ON messages(date)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"База данных {self.db_name} инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    def save_message(
        self,
        message_id: int,
        chat_id: int,
        sender: Optional[str],
        text: Optional[str],
        date: datetime
    ) -> bool:
        """
        Сохраняет сообщение в базу данных с проверкой на дубликаты.
        
        Args:
            message_id: ID сообщения в Telegram
            chat_id: ID чата
            sender: Имя отправителя
            text: Текст сообщения
            date: Дата и время сообщения
            
        Returns:
            bool: True если сообщение сохранено, False если уже существует
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Пытаемся вставить сообщение
            # Используем INSERT OR IGNORE для автоматической проверки дублей
            cursor.execute("""
                INSERT OR IGNORE INTO messages (id, chat_id, sender, text, date)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, chat_id, sender, text, date))
            
            conn.commit()
            was_inserted = cursor.rowcount > 0
            conn.close()
            
            if was_inserted:
                logger.debug(f"Сообщение {message_id} из чата {chat_id} сохранено в БД")
            else:
                logger.debug(f"Сообщение {message_id} из чата {chat_id} уже существует в БД")
            
            return was_inserted
        except sqlite3.IntegrityError:
            # Сообщение уже существует (дубликат)
            logger.debug(f"Дубликат сообщения {message_id} из чата {chat_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения в БД: {e}")
            return False
    
    def get_message_count(self, chat_id: Optional[int] = None) -> int:
        """
        Возвращает количество сообщений в базе данных.
        
        Args:
            chat_id: Если указан, возвращает количество сообщений для конкретного чата
            
        Returns:
            int: Количество сообщений
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if chat_id:
                cursor.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ?", (chat_id,))
            else:
                cursor.execute("SELECT COUNT(*) FROM messages")
            
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Ошибка при получении количества сообщений: {e}")
            return 0

