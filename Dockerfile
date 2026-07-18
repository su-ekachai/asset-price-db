FROM python:3.12-slim

LABEL maintainer="Ekachai Suriyakriengkri" \
      description="OHLCV market data store using QuestDB" \
      version="1.0.0"

WORKDIR /app

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies as root
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy application code
COPY src/ src/
COPY main.py .

# Create non-root user
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python main.py check health || exit 1

# Signal handling
STOPSIGNAL SIGTERM

ENTRYPOINT ["uv", "run", "python", "main.py"]
