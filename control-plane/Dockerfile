FROM python:3.13-slim

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appuser /app && chmod +x /app/entrypoint.sh
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import httpx; r = httpx.get('http://localhost:9090/health'); r.raise_for_status()"

EXPOSE 9090

ENTRYPOINT ["/app/entrypoint.sh"]
