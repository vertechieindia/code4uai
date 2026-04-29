FROM python:3.11-slim AS base
WORKDIR /app
RUN pip install poetry==1.7.1 && poetry config virtualenvs.create false

FROM base AS builder
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-dev --no-root

FROM base AS runtime
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY backend/src /app/src
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "code4u.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
