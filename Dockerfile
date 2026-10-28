# This image was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIEWPIE_BASE_URL=http://127.0.0.1:8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY viewpie_layout_engine ./viewpie_layout_engine

RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/health', timeout=3).raise_for_status()"

CMD ["uvicorn", "viewpie_layout_engine.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
