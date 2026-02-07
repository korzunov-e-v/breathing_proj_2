# src/llm/openrouter_client.py
from __future__ import annotations

import httpx

from src.settings import settings


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    pass


async def generate_comment_reply(*, system_prompt: str, user_comment: str) -> str:
    token = settings.openrouter_token
    if not token:
        raise OpenRouterError("OPENROUTER_TOKEN не задан")

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_comment},
        ],
        "temperature": 0.7,
        "max_tokens": 250,
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
