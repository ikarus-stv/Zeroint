"""
Основной модуль Telegram клиента на базе Telethon.

Реализует:
- Подключение к Telegram
- Получение списка диалогов
- Сбор последних N сообщений из чата
- Обработку новых сообщений в реальном времени
- Сохранение сообщений в локальную базу данных
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import User, Chat, Channel
from telethon.tl.types import PeerUser, PeerChat, PeerChannel

import config
from db import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_client.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()


class TelegramBot:
    """Класс для работы с Telegram через Telethon."""
    
    def __init__(self, api_id: int, api_hash: str, session_name: str):
        """
        Инициализация Telegram клиента.
        
        Args:
            api_id: API ID от Telegram
            api_hash: API Hash от Telegram
            session_name: Имя файла сессии
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.is_running = False
    
    @staticmethod
    def get_chat_id_from_message(message) -> Optional[int]:
        """
        Извлекает chat_id из сообщения, обрабатывая разные типы peer_id.
        
        Args:
            message: Объект сообщения Telethon
            
        Returns:
            Optional[int]: ID чата или None
        """
        if not message:
            return None
        
        # Пробуем получить chat_id напрямую
        if hasattr(message, 'chat_id') and message.chat_id:
            return message.chat_id
        
        # Обрабатываем peer_id
        if hasattr(message, 'peer_id') and message.peer_id:
            peer = message.peer_id
            
            if isinstance(peer, PeerChannel):
                return peer.channel_id
            elif isinstance(peer, PeerChat):
                return peer.chat_id
            elif isinstance(peer, PeerUser):
                return peer.user_id
        
        # Если ничего не помогло, пробуем через to_id
        if hasattr(message, 'to_id') and message.to_id:
            peer = message.to_id
            if isinstance(peer, PeerChannel):
                return peer.channel_id
            elif isinstance(peer, PeerChat):
                return peer.chat_id
            elif isinstance(peer, PeerUser):
                return peer.user_id
        
        return None
    
    @staticmethod
    def is_private_chat(message) -> bool:
        """
        Определяет, является ли сообщение из личного чата.
        
        Args:
            message: Объект сообщения Telethon
            
        Returns:
            bool: True если это личное сообщение, False если группа/канал
        """
        if not message:
            return False
        
        # Проверяем peer_id
        if hasattr(message, 'peer_id') and message.peer_id:
            return isinstance(message.peer_id, PeerUser)
        
        # Проверяем to_id
        if hasattr(message, 'to_id') and message.to_id:
            return isinstance(message.to_id, PeerUser)
        
        return False
    
    async def connect(self):
        """Подключение к Telegram с обработкой ошибок."""
        try:
            await self.client.start()
            logger.info("Успешное подключение к Telegram")
            
            # Проверяем авторизацию
            if not await self.client.is_user_authorized():
                logger.warning("Пользователь не авторизован. Начнется процесс авторизации...")
                phone = input("Введите номер телефона: ")
                await self.client.send_code_request(phone)
                
                code = input("Введите код подтверждения: ")
                try:
                    await self.client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("Введите пароль двухфакторной аутентификации: ")
                    await self.client.sign_in(password=password)
            
            me = await self.client.get_me()
            logger.info(f"Авторизован как: {me.first_name} {me.last_name or ''} (@{me.username or 'без username'})")
            return True
            
        except FloodWaitError as e:
            logger.error(f"Превышен лимит запросов. Ожидание {e.seconds} секунд...")
            await asyncio.sleep(e.seconds)
            return await self.connect()
        except Exception as e:
            logger.error(f"Ошибка при подключении к Telegram: {e}")
            return False
    
    async def get_dialogs(self, limit: int = 20) -> List:
        """
        Получает список доступных диалогов (чатов).
        
        Args:
            limit: Максимальное количество диалогов для получения
            
        Returns:
            List: Список диалогов
        """
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=limit):
                dialogs.append(dialog)
            
            logger.info(f"Получено {len(dialogs)} диалогов")
            return dialogs
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка диалогов: {e}")
            return []
    
    def print_dialogs(self, dialogs: List):
        """
        Выводит список диалогов в консоль.
        
        Args:
            dialogs: Список диалогов
        """
        print("\n" + "="*60)
        print("ДОСТУПНЫЕ ДИАЛОГИ:")
        print("="*60)
        
        for i, dialog in enumerate(dialogs, 1):
            chat_title = dialog.name
            chat_id = dialog.id
            unread_count = dialog.unread_count
            
            print(f"{i}. {chat_title} (ID: {chat_id}) [Непрочитано: {unread_count}]")
        
        print("="*60 + "\n")
    
    async def get_chat_messages(self, chat_id: int, limit: int = 100) -> List:
        """
        Получает последние N сообщений из указанного чата.
        
        Args:
            chat_id: ID чата
            limit: Количество сообщений для получения
            
        Returns:
            List: Список сообщений
        """
        try:
            messages = []
            async for message in self.client.iter_messages(chat_id, limit=limit):
                messages.append(message)
            
            logger.info(f"Получено {len(messages)} сообщений из чата {chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из чата {chat_id}: {e}")
            return []
    
    async def save_messages_to_db(self, messages: List, chat_title: str = ""):
        """
        Сохраняет список сообщений в базу данных.
        
        Args:
            messages: Список сообщений
            chat_title: Название чата (для логирования)
        """
        saved_count = 0
        skipped_count = 0
        
        for message in messages:
            if message.text:  # Сохраняем только текстовые сообщения
                chat_id = self.get_chat_id_from_message(message)
                if not chat_id:
                    logger.warning(f"Не удалось определить chat_id для сообщения {message.id}")
                    continue
                
                # Определяем sender_name в зависимости от типа чата
                sender_name = None
                
                if self.is_private_chat(message):
                    # Для личных сообщений используем имя отправителя
                    sender = None
                    
                    # Пытаемся получить отправителя из сообщения
                    if message.sender:
                        sender = message.sender
                    else:
                        # Если sender не загружен, пытаемся загрузить его явно
                        try:
                            sender = await message.get_sender()
                        except Exception as e:
                            logger.debug(f"Не удалось получить отправителя через get_sender(): {e}")
                            # Если не получилось, пробуем получить через chat_id (для личных чатов chat_id = user_id)
                            try:
                                sender = await self.client.get_entity(chat_id)
                            except Exception as e2:
                                logger.warning(f"Не удалось получить информацию об отправителе {chat_id}: {e2}")
                    
                    # Формируем имя отправителя
                    if sender:
                        if isinstance(sender, User):
                            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                            if not sender_name:
                                sender_name = sender.username or "Неизвестный"
                        else:
                            sender_name = str(sender)
                    else:
                        sender_name = "Неизвестный"
                else:
                    # Для групп и каналов используем название чата
                    # Пытаемся получить информацию о чате
                    try:
                        chat = await self.client.get_entity(chat_id)
                        if hasattr(chat, 'title'):
                            sender_name = chat.title
                        elif hasattr(chat, 'first_name'):
                            sender_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip()
                        else:
                            sender_name = chat_title or "Неизвестный чат"
                    except Exception as e:
                        logger.warning(f"Не удалось получить информацию о чате {chat_id}: {e}")
                        sender_name = chat_title or "Неизвестный чат"
                
                was_saved = db.save_message(
                    message_id=message.id,
                    chat_id=chat_id,
                    sender=sender_name,
                    text=message.text,
                    date=message.date
                )
                
                if was_saved:
                    saved_count += 1
                else:
                    skipped_count += 1
        
        logger.info(f"Сохранено {saved_count} новых сообщений из '{chat_title}', пропущено {skipped_count} дубликатов")
    
    async def setup_new_message_handler(self):
        """Настраивает обработчик новых сообщений в реальном времени."""
        
        @self.client.on(events.NewMessage)
        async def handler(event):
            """Обработчик новых сообщений."""
            try:
                message = event.message
                chat = await event.get_chat()
                
                # Получаем название чата
                chat_title = chat.title if hasattr(chat, 'title') else (
                    f"{chat.first_name or ''} {chat.last_name or ''}".strip() if hasattr(chat, 'first_name') else "Неизвестный чат"
                )
                
                # Определяем sender_name для сохранения в БД
                # Для личных сообщений - имя отправителя, для групп/каналов - название чата
                sender_name = "Неизвестный"
                
                if self.is_private_chat(message):
                    # Для личных сообщений используем имя отправителя
                    sender = None
                    
                    # Пытаемся получить отправителя из сообщения
                    if message.sender:
                        sender = message.sender
                    else:
                        # Если sender не загружен, пытаемся загрузить его явно
                        try:
                            sender = await message.get_sender()
                        except Exception as e:
                            logger.debug(f"Не удалось получить отправителя через get_sender(): {e}")
                            # Если не получилось, пробуем получить через chat (для личных чатов)
                            try:
                                if isinstance(chat, User):
                                    sender = chat
                            except Exception as e2:
                                logger.warning(f"Не удалось получить информацию об отправителе: {e2}")
                    
                    # Формируем имя отправителя
                    if sender:
                        if isinstance(sender, User):
                            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                            if not sender_name:
                                sender_name = sender.username or "Неизвестный"
                        else:
                            sender_name = str(sender)
                    else:
                        sender_name = "Неизвестный"
                else:
                    # Для групп и каналов используем название чата
                    sender_name = chat_title
                
                # Получаем имя отправителя для вывода в консоль
                console_sender = "Неизвестный"
                sender_for_console = None
                
                if message.sender:
                    sender_for_console = message.sender
                else:
                    try:
                        sender_for_console = await message.get_sender()
                    except Exception:
                        pass
                
                if sender_for_console:
                    if isinstance(sender_for_console, User):
                        console_sender = f"{sender_for_console.first_name or ''} {sender_for_console.last_name or ''}".strip()
                        if not console_sender:
                            console_sender = sender_for_console.username or "Неизвестный"
                    else:
                        console_sender = str(sender_for_console)
                
                # Получаем текст сообщения
                text = message.text or "[Медиа-сообщение]"
                
                # Выводим в консоль
                print(f"[{chat_title}] {console_sender}: {text}")
                
                # Сохраняем в базу данных
                if message.text:  # Сохраняем только текстовые сообщения
                    chat_id = self.get_chat_id_from_message(message)
                    if chat_id:
                        db.save_message(
                            message_id=message.id,
                            chat_id=chat_id,
                            sender=sender_name,
                            text=message.text,
                            date=message.date
                        )
                
            except Exception as e:
                logger.error(f"Ошибка при обработке нового сообщения: {e}")
        
        logger.info("Обработчик новых сообщений настроен")
    
    async def start_listening(self):
        """Запускает прослушивание новых сообщений."""
        if self.is_running:
            logger.warning("Прослушивание уже запущено")
            return
        
        await self.setup_new_message_handler()
        self.is_running = True
        logger.info("Начато прослушивание новых сообщений...")
        print("\n[LIVE] Ожидание новых сообщений... (Ctrl+C для остановки)\n")
        
        # Запускаем клиент и ждем сообщений
        await self.client.run_until_disconnected()
    
    async def disconnect(self):
        """Отключение от Telegram."""
        try:
            await self.client.disconnect()
            logger.info("Отключено от Telegram")
        except Exception as e:
            logger.error(f"Ошибка при отключении: {e}")


async def main():
    """Основная функция с примерами использования."""
    
    # Инициализация клиента
    bot = TelegramBot(
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_name=config.SESSION_NAME
    )
    
    try:
        # Подключение к Telegram
        if not await bot.connect():
            logger.error("Не удалось подключиться к Telegram")
            return
        
        # Пример 1: Получение списка чатов
        print("\n" + "="*60)
        print("ПРИМЕР 1: Получение списка доступных чатов")
        print("="*60)
        dialogs = await bot.get_dialogs(limit=20)
        bot.print_dialogs(dialogs)
        
        if not dialogs:
            print("Нет доступных диалогов")
            return
        
        # Пример 2: Сбор последних 100 сообщений из выбранного чата
        print("="*60)
        print("ПРИМЕР 2: Сбор последних 100 сообщений из чата")
        print("="*60)
        
        # Выбираем первый чат для примера (можно изменить на любой другой)
        selected_dialog = dialogs[0]
        chat_id = selected_dialog.id
        chat_title = selected_dialog.name
        
        print(f"Выбран чат: {chat_title} (ID: {chat_id})")
        print("Получение сообщений...")
        
        messages = await bot.get_chat_messages(chat_id, limit=100)
        print(f"Получено {len(messages)} сообщений")
        
        # Сохраняем сообщения в базу данных
        await bot.save_messages_to_db(messages, chat_title)
        
        # Показываем статистику базы данных
        total_messages = db.get_message_count()
        chat_messages = db.get_message_count(chat_id)
        print(f"\nСтатистика БД:")
        print(f"  Всего сообщений: {total_messages}")
        print(f"  Сообщений из '{chat_title}': {chat_messages}")
        
        # Пример 3: Запуск live-слушателя новых сообщений
        print("\n" + "="*60)
        print("ПРИМЕР 3: Запуск live-слушателя новых сообщений")
        print("="*60)
        print("Нажмите Enter для запуска прослушивания...")
        input()
        
        await bot.start_listening()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.disconnect()
        logger.info("Программа завершена")


if __name__ == "__main__":
    # Запуск основной функции
    asyncio.run(main())

