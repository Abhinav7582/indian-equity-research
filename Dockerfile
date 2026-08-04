# ---------------------------------------------------------------------------
# Reproducible development / CI image.
#
# This image runs tests and static analysis. It is NOT a deployment artefact:
# the project has no service to deploy and no trading functionality.
# ---------------------------------------------------------------------------

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv is copied from its official distroless image; no curl-pipe-to-shell.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependency layer: cached unless the lockfile or project metadata changes.
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --extra dev --no-install-project

# Source layer.
COPY . .
RUN uv sync --extra dev

ENV PATH="/opt/venv/bin:${PATH}"

# Default to the full check suite so `docker run <image>` is meaningful.
CMD ["sh", "-c", "ruff check . && ruff format --check . && mypy && pytest -m 'not integration'"]
