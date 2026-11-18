# The sketches as one image. Data is mounted at /data (fetch it with app/fetch_data.py first).
# uv 0.9.30, Python 3.13.11
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 DATA_DIR=/data
COPY app/pyproject.toml app/uv.lock ./
RUN uv sync --frozen --no-install-project
COPY app/ ./
USER 1000:1000
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
