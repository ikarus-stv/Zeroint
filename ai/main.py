"""
CLI-приложение для получения краткой выжимки текста через GigaChat API.

Использование:
    python main.py summary --file messages.txt
    python main.py summary --text "любые сообщения"
"""

import argparse
import sys
import logging
from typing import Optional

from gigachat import generate_summary, GigaChatError, GigaChatAuthError, GigaChatAPIError
from utils import read_file, validate_text, format_output

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_text_from_input(file_path: Optional[str] = None, text: Optional[str] = None) -> str:
    """
    Получает текст из файла или аргумента командной строки.
    
    Args:
        file_path: Путь к файлу
        text: Текст напрямую
        
    Returns:
        str: Текст для обработки
        
    Raises:
        ValueError: Если не указан ни файл, ни текст
        FileNotFoundError: Если файл не найден
        IOError: Если произошла ошибка при чтении файла
    """
    # Приоритет у --text
    if text:
        if not validate_text(text):
            raise ValueError("Текст не может быть пустым")
        logger.info("Использован текст из аргумента --text")
        return text
    
    if file_path:
        content = read_file(file_path)
        if not validate_text(content):
            raise ValueError(f"Файл {file_path} пуст или содержит только пробелы")
        return content
    
    raise ValueError("Необходимо указать либо --file, либо --text")


def summary_command(args):
    """
    Обрабатывает команду summary.
    
    Args:
        args: Аргументы командной строки
    """
    try:
        # Получаем текст для обработки
        text = get_text_from_input(args.file, args.text)
        
        logger.info(f"Обработка текста (длина: {len(text)} символов)...")
        
        # Генерируем выжимку
        summary = generate_summary(text)
        
        # Выводим результат
        print("\n" + "="*80)
        print("КРАТКАЯ ВЫЖИМКА:")
        print("="*80)
        print(format_output(summary))
        print("="*80 + "\n")
        
        logger.info("Выжимка успешно сгенерирована и выведена")
        
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Ошибка при чтении файла: {e}", file=sys.stderr)
        sys.exit(1)
    except GigaChatAuthError as e:
        print(f"Ошибка аутентификации: {e}", file=sys.stderr)
        print("\nПроверьте, что в .env файле указаны правильные CLIENT_ID и CLIENT_SECRET", file=sys.stderr)
        sys.exit(1)
    except GigaChatAPIError as e:
        print(f"Ошибка API: {e}", file=sys.stderr)
        sys.exit(1)
    except GigaChatError as e:
        print(f"Ошибка GigaChat: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("Неожиданная ошибка")
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """
    Создает парсер аргументов командной строки.
    
    Returns:
        argparse.ArgumentParser: Парсер аргументов
    """
    parser = argparse.ArgumentParser(
        description="CLI-инструмент для получения краткой выжимки текста через GigaChat API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py summary --file messages.txt
  python main.py summary --text "Ваш текст здесь"
  python main.py summary --file data.txt --text "приоритет у --text"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда summary
    summary_parser = subparsers.add_parser(
        'summary',
        help='Генерирует краткую выжимку текста'
    )
    
    summary_parser.add_argument(
        '--file',
        type=str,
        help='Путь к файлу с текстом для обработки'
    )
    
    summary_parser.add_argument(
        '--text',
        type=str,
        help='Текст для обработки (приоритет над --file)'
    )
    
    return parser


def main():
    """Главная функция приложения."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'summary':
        summary_command(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
