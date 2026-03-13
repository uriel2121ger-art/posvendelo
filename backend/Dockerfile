FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/uriel2121ger-art/titan-pos"
LABEL org.opencontainers.image.description="POSVENDELO backend API"

WORKDIR /app

# System deps for lxml/signxml (CFDI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc \
    cups-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

RUN chown -R appuser:appuser /app && chmod +x /app/entrypoint.sh
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python3 -c "import httpx; r = httpx.get('http://localhost:8000/health'); r.raise_for_status()"

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
