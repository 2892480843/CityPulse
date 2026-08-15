FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system citypulse && adduser --system --ingroup citypulse citypulse
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .
USER citypulse
EXPOSE 8000
CMD ["uvicorn", "citypulse.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
