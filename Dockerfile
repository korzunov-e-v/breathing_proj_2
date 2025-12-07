FROM python:3.14-slim AS builder

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv (ультрабыстрый пакетный менеджер)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Копируем файлы зависимостей для кэширования
COPY pyproject.toml uv.lock ./

# Создаем виртуальное окружение и устанавливаем зависимости
RUN uv venv --python 3.14
RUN uv sync --frozen --no-dev



FROM python:3.14-slim AS runtime

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем виртуальное окружение из билдера
COPY --from=builder /app/.venv ./.venv

# Копируем исходный код
COPY . .

# Настраиваем переменные окружения
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"
ENV PYTHONUNBUFFERED="1"
