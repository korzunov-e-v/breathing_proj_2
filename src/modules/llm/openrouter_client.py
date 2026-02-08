# src/llm/openrouter_client.py
from __future__ import annotations

import httpx

from src.settings import settings


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    pass


async def generate_comment_reply(*, system_prompt: str, user_comment: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_comment},
    ]
    return await chat_with_context(messages=messages)


async def chat_with_context(*, messages: list[dict[str, str]], system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 250) -> str:
    """
    Отправляет список сообщений в OpenRouter API и возвращает ответ.

    Args:
        messages: Список словарей с ключами 'role' и 'content'
        system_prompt: Системный промпт, который будет добавлен в начало сообщений (по умолчанию settings.prompt)
        temperature: Параметр температуры для генерации
        max_tokens: Максимальное количество токенов в ответе

    Returns:
        Текст ответа от AI
    """
    token = settings.openrouter_token
    if not token:
        raise OpenRouterError("OPENROUTER_TOKEN не задан")

    # Добавляем системный промпт если он задан
    if system_prompt is None:
        system_prompt = settings.openrouter_comment_prompt

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        if r.status_code >= 400:
            raise OpenRouterError(f"OpenRouter HTTP {r.status_code}: {r.text}")

        data = r.json()
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            raise OpenRouterError(f"Неожиданный формат ответа OpenRouter: {e}. Body={data}")

