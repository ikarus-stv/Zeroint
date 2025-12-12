"""
Вспомогательные функции для работы с файлами и текстом.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def read_file(file_path: str) -> str:
    """
    Читает содержимое текстового файла.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        str: Содержимое файла
        
    Raises:
        FileNotFoundError: Если файл не найден
        IOError: Если произошла ошибка при чтении файла
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    if not os.path.isfile(file_path):
        raise ValueError(f"Указанный путь не является файлом: {file_path}")
    
    try:
        logger.info(f"Чтение файла: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            logger.warning(f"Файл {file_path} пуст")
        
        return content
        
    except UnicodeDecodeError:
        # Пробуем другие кодировки
        try:
            with open(file_path, 'r', encoding='cp1251') as f:
                content = f.read()
            logger.info(f"Файл прочитан с кодировкой cp1251")
            return content
        except Exception as e:
            raise IOError(f"Не удалось прочитать файл {file_path}: {e}")
    except Exception as e:
        raise IOError(f"Ошибка при чтении файла {file_path}: {e}")


def validate_text(text: str) -> bool:
    """
    Проверяет, что текст не пустой.
    
    Args:
        text: Текст для проверки
        
    Returns:
        bool: True если текст валиден
    """
    return bool(text and text.strip())


def format_output(summary: str, width: int = 80) -> str:
    """
    Форматирует вывод выжимки для красивого отображения.
    
    Args:
        summary: Текст выжимки
        width: Ширина вывода
        
    Returns:
        str: Отформатированный текст
    """
    # Простое форматирование - разбиваем на строки по ширине
    lines = []
    words = summary.split()
    current_line = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 для пробела
        if current_length + word_length <= width:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)

