FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src ./src
COPY frontend ./frontend
COPY run_web.py run_bot.py alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV PYTHONPATH=/app/src
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"
CMD ["python", "run_web.py"]
