import os
import time
import requests
import telebot
from telebot import formatting
from dotenv import load_dotenv

load_dotenv()

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GIGACHAT_BASIC_AUTH = os.getenv("GIGACHAT_BASIC_AUTH")  # без слова "Basic"
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
CLIENT_ID = os.getenv("CLIENT_ID")  # используется как RqUID
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat")

# =========================
# Checks
# =========================
missing = [k for k, v in {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "GIGACHAT_BASIC_AUTH": GIGACHAT_BASIC_AUTH,
    "CLIENT_ID": CLIENT_ID,
}.items() if not v]

if missing:
    raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}")

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_BASE = "https://gigachat.devices.sberbank.ru/api/v1"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")


class GigaChatClient:
    def __init__(self, basic_auth: str, scope: str, rq_uid: str):
        self.basic_auth = basic_auth
        self.scope = scope
        self.rq_uid = rq_uid

        self.access_token: str | None = None
        self.expires_at: float = 0.0  # epoch seconds

    def _need_refresh(self) -> bool:
        # обновляем заранее на 30 секунд
        return (not self.access_token) or (time.time() >= self.expires_at - 30)

    def refresh_token(self) -> None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": self.rq_uid,  # <-- строго из .env (CLIENT_ID)
            "Authorization": f"Basic {self.basic_auth}",
        }
        data = {"scope": self.scope}

        resp = requests.post(OAUTH_URL, headers=headers, data=data, verify=False, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"Не пришёл access_token. Ответ: {payload}")

        self.access_token = token

        # expires_at (иногда мс), либо expires_in
        if "expires_at" in payload:
            exp = payload["expires_at"]
            self.expires_at = exp / 1000 if exp > 10_000_000_000 else float(exp)
        elif "expires_in" in payload:
            self.expires_at = time.time() + int(payload["expires_in"])
        else:
            self.expires_at = time.time() + 900  # запасной вариант

    def _headers(self) -> dict:
        if self._need_refresh():
            self.refresh_token()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def chat(self, user_text: str, model: str) -> str:
        url = f"{API_BASE}/chat/completions"
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент."},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.7,
            "max_tokens": 800,
        }

        headers = self._headers()
        resp = requests.post(url, headers=headers, json=body, verify=False, timeout=60)

        # если токен протух — обновим и повторим 1 раз
        if resp.status_code == 401:
            self.refresh_token()
            headers = self._headers()
            resp = requests.post(url, headers=headers, json=body, verify=False, timeout=60)

        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return f"Неожиданный формат ответа GigaChat: {data}"

    def list_models(self):
        url = f"{API_BASE}/models"
        headers = self._headers()
        resp = requests.get(url, headers=headers, verify=False, timeout=30)

        if resp.status_code == 401:
            self.refresh_token()
            headers = self._headers()
            resp = requests.get(url, headers=headers, verify=False, timeout=30)

        resp.raise_for_status()
        return resp.json()


gigachat = GigaChatClient(
    basic_auth=GIGACHAT_BASIC_AUTH,
    scope=GIGACHAT_SCOPE,
    rq_uid=CLIENT_ID
)


@bot.message_handler(commands=["start", "help"])
def start(m):
    bot.send_message(
        m.chat.id,
        "Привет! Напиши вопрос — я отправлю его в GigaChat и верну ответ.\n\n"
        "Команды:\n"
        "/models — показать модели\n"
        "/setmodel <имя> — выбрать модель"
    )


@bot.message_handler(commands=["models"])
def models(m):
    try:
        data = gigachat.list_models()
        escaped = formatting.escape_html(str(data)[:3500])
        text = f"<b>Ответ /models:</b>\n<code>{escaped}</code>"
        bot.send_message(m.chat.id, text)
    except Exception as e:
        bot.send_message(
            m.chat.id,
            f"Ошибка при получении моделей: <code>{formatting.escape_html(str(e))}</code>",
        )


@bot.message_handler(commands=["setmodel"])
def setmodel(m):
    global GIGACHAT_MODEL
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Использование: /setmodel <имя_модели>")
        return
    GIGACHAT_MODEL = parts[1].strip()
    bot.send_message(
        m.chat.id,
        f"Ок, текущая модель: <b>{formatting.escape_html(GIGACHAT_MODEL)}</b>",
    )


@bot.message_handler(content_types=["text"])
def handle_text(m):
    user_text = (m.text or "").strip()
    if not user_text:
        return

    bot.send_chat_action(m.chat.id, "typing")

    try:
        answer = gigachat.chat(user_text, model=GIGACHAT_MODEL)
        if len(answer) > 4000:
            answer = answer[:4000] + "\n...\n(обрезано)"
        bot.send_message(m.chat.id, formatting.escape_html(answer))
    except requests.HTTPError as e:
        try:
            body = e.response.text
        except Exception:
            body = str(e)
        bot.send_message(
            m.chat.id,
            f"HTTP ошибка от GigaChat: <code>{formatting.escape_html(body)}</code>",
        )
    except Exception as e:
        bot.send_message(
            m.chat.id,
            f"Ошибка: <code>{formatting.escape_html(str(e))}</code>",
        )


if __name__ == "__main__":
    bot.infinity_polling(timeout=30, long_polling_timeout=30)
