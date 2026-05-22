FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

COPY . .
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["ag"]
CMD ["--help"]
