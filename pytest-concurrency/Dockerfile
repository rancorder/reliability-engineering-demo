FROM python:3.11-slim

WORKDIR /tests

RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    pytest-asyncio==0.21.1 \
    httpx==0.25.2 \
    sqlalchemy[asyncio]==2.0.25 \
    asyncpg==0.29.0

COPY tests /tests

CMD ["pytest", "-v", "/tests"]