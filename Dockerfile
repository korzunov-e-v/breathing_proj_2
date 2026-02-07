FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Копируем файлы зависимостей для кэширования
COPY pyproject.toml uv.lock ./

# Создаем виртуальное окружение и устанавливаем зависимости
RUN uv venv --python 3.14 /app/.venv
RUN uv sync --frozen



FROM python:3.14-slim AS runtime

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .
COPY --from=builder /app/.venv /app/.venv

# Настраиваем переменные окружения
ENV PATH="/root/.local/bin/:$PATH"
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"
ENV PYTHONUNBUFFERED="1"
