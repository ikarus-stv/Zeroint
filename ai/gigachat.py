"""
Модуль для работы с GigaChat API.

Реализует:
- Получение OAuth токена
- Генерацию краткой выжимки (summary) текста
"""

import os
import base64
import logging
import requests
from typing import Optional
from dotenv import load_dotenv
import urllib3

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Отключаем предупреждения о небезопасных запросах (для корпоративных сетей)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL эндпоинтов GigaChat API
OAUTH_URL = "https://gigachat.devices.sberbank.ru/api/v1/oauth"
CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# Опция для отключения проверки SSL (для корпоративных сетей с самоподписанными сертификатами)
SSL_VERIFY = os.getenv("SSL_VERIFY", "false").lower() == "true"


class GigaChatError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAuthError(GigaChatError):
    """Ошибка аутентификации в GigaChat API."""
    pass


class GigaChatAPIError(GigaChatError):
    """Ошибка при запросе к GigaChat API."""
    pass


def get_access_token() -> str:
    """
    Получает OAuth токен для доступа к GigaChat API.
    
    Returns:
        str: Access token
        
    Raises:
        GigaChatAuthError: Если не удалось получить токен
    """
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise GigaChatAuthError(
            "CLIENT_ID и CLIENT_SECRET должны быть установлены в .env файле"
        )
    
    # Кодируем credentials в base64 для Basic Auth
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    data = {
        "scope": "GIGACHAT_API_PERS"
    }
    
    try:
        logger.info(f"Запрос OAuth токена к {OAUTH_URL} (SSL verify: {SSL_VERIFY})...")
        response = requests.post(
            OAUTH_URL, 
            headers=headers, 
            data=data, 
            timeout=30,
            verify=SSL_VERIFY
        )
        response.raise_for_status()
        
        result = response.json()
        access_token = result.get("access_token")
        
        if not access_token:
            raise GigaChatAuthError("Токен не найден в ответе API")
        
        logger.info("OAuth токен успешно получен")
        return access_token
        
    except requests.exceptions.SSLError as e:
        logger.error(f"Ошибка SSL при запросе токена: {e}")
        error_msg = (
            f"Ошибка проверки SSL сертификата: {e}\n"
            "Если вы находитесь в корпоративной сети, добавьте в .env файл: SSL_VERIFY=false"
        )
        raise GigaChatAuthError(error_msg)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе токена: {e}")
        raise GigaChatAuthError(f"Не удалось получить токен: {e}")
    except KeyError as e:
        logger.error(f"Неожиданный формат ответа API: {e}")
        raise GigaChatAuthError(f"Неожиданный формат ответа API: {e}")


def generate_summary(text: str) -> str:
    """
    Генерирует краткую выжимку (summary) для переданного текста.
    
    Args:
        text: Текст для обработки
        
    Returns:
        str: Краткая выжимка текста
        
    Raises:
        GigaChatAPIError: Если произошла ошибка при запросе к API
        GigaChatAuthError: Если произошла ошибка аутентификации
    """
    if not text or not text.strip():
        raise ValueError("Текст не может быть пустым")
    
    # Получаем токен доступа
    try:
        access_token = get_access_token()
    except GigaChatAuthError as e:
        raise
    
    # Формируем запрос к chat/completions
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {
                "role": "system",
                "content": "Ты – ассистент, который делает краткие выжимки текста. "
                          "Создай краткую и информативную выжимку основных мыслей и фактов из текста."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.3,  # Низкая температура для более точных и кратких ответов
        "max_tokens": 500  # Ограничение длины ответа
    }
    
    try:
        logger.info("Отправка запроса к GigaChat API для генерации выжимки...")
        response = requests.post(
            CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
            verify=SSL_VERIFY
        )
        
        # Проверяем статус ответа
        if response.status_code == 401:
            raise GigaChatAuthError("Ошибка аутентификации. Проверьте CLIENT_ID и CLIENT_SECRET")
        elif response.status_code == 429:
            raise GigaChatAPIError("Превышен лимит запросов. Попробуйте позже.")
        elif response.status_code >= 400:
            error_text = response.text
            logger.error(f"Ошибка API (код {response.status_code}): {error_text}")
            raise GigaChatAPIError(f"Ошибка API: {response.status_code} - {error_text}")
        
        response.raise_for_status()
        result = response.json()
        
        # Извлекаем текст ответа
        choices = result.get("choices", [])
        if not choices:
            raise GigaChatAPIError("Пустой ответ от API")
        
        summary = choices[0].get("message", {}).get("content", "")
        
        if not summary:
            raise GigaChatAPIError("Выжимка не найдена в ответе API")
        
        logger.info("Выжимка успешно получена")
        return summary.strip()
        
    except requests.exceptions.Timeout:
        raise GigaChatAPIError("Превышено время ожидания ответа от API")
    except requests.exceptions.SSLError as e:
        logger.error(f"Ошибка SSL при запросе к API: {e}")
        error_msg = (
            f"Ошибка проверки SSL сертификата: {e}\n"
            "Если вы находитесь в корпоративной сети, добавьте в .env файл: SSL_VERIFY=false"
        )
        raise GigaChatAPIError(error_msg)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        raise GigaChatAPIError(f"Ошибка при запросе к API: {e}")
    except KeyError as e:
        logger.error(f"Неожиданный формат ответа API: {e}")
        raise GigaChatAPIError(f"Неожиданный формат ответа API: {e}")

