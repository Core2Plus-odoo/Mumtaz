FROM python:3.12-slim

# Security: non-root user
RUN groupadd -r mumtaz && useradd -r -g mumtaz -d /app mumtaz

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=mumtaz:mumtaz . .

# Runtime as non-root
USER mumtaz

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
