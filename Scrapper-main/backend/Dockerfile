FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir \
    'fastapi>=0.115' \
    'uvicorn[standard]>=0.32' \
    'sqlalchemy[asyncio]>=2.0.36' \
    asyncpg \
    'alembic>=1.14' \
    pydantic \
    pydantic-settings \
    httpx \
    beautifulsoup4 \
    redis \
    celery \
    python-dotenv \
    'psycopg[binary]>=3.2' \
    'openpyxl>=3.1' \
    'python-multipart>=0.0.12'

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
