FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin libgdal-dev libgeos-dev libproj-dev gettext \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /bin/uv

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# No database needed: settings have import-time defaults for everything.
# tailwind build downloads the Tailwind CLI binary for the image architecture (network required).
RUN python manage.py tailwind build \
    && python manage.py collectstatic --noinput \
    && python manage.py compilemessages --ignore=.venv

ENV PORT=8000
CMD gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2
