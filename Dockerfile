FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY chronicle_guard ./chronicle_guard
COPY static ./static
RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn chronicle_guard.app:app --host 0.0.0.0 --port ${PORT}"]
