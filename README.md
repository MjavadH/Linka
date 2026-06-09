# Linka

Linka is a production-oriented, open-source Telegram bot foundation for secure file delivery through Telegram deep links. It is designed as a gateway between Telegram channels and users: a user opens a link such as `https://t.me/linka_bot?start=quality_1080_123`, Linka validates the token, checks sponsor-channel membership and premium eligibility, sends the stored Telegram `file_id`, and schedules automatic deletion of the delivered message.

## Architecture

The codebase follows Clean Architecture boundaries:

- `src/bot` — application entrypoint and aiogram bootstrap.
- `src/core` — configuration and cross-cutting infrastructure.
- `src/database` — SQLAlchemy async engine/session setup and declarative base.
- `src/models` — normalized SQLAlchemy 2.x ORM models.
- `src/repositories` — database access logic only.
- `src/services` — business workflows: delivery, sponsor checks, premium, payments, posts, broadcasts.
- `src/handlers` — aiogram routers; handlers orchestrate services and contain no domain logic.
- `src/middlewares` — aiogram dependency-injection and access-control middleware.
- `src/keyboards` — Telegram keyboard builders.
- `src/scheduler` — APScheduler jobs for restart-safe background work.
- `src/migrations` — Alembic environment and versioned migrations.
- `src/tests` — automated tests.

## Core capabilities

- Deep-link file delivery with token validation.
- Multiple sponsor channel requirements with priority, activation flags, campaign date windows, and target-member expiration.
- Premium subscriptions with manual extension support.
- Premium-only files and premium-only quality variants.
- Manual payment-request workflow with proof metadata and admin review states.
- Restart-safe temporary message deletion using persisted `temporary_messages` rows and APScheduler.
- API-ready service layer for a future FastAPI admin panel.
- Post generator service for Telegram-ready HTML text and inline deep-link buttons.
- Broadcast service foundation supporting text, photo, video, document, and `copy_message` payloads with rate limiting.
- Download statistics stored per user, file, file variant, token, and premium/free status.

## Database schema

The initial Alembic migration creates these normalized PostgreSQL tables:

- `users`
- `files`
- `file_variants`
- `deep_links`
- `sponsors`
- `sponsor_campaigns`
- `sponsor_requirements`
- `subscriptions`
- `payment_requests`
- `downloads`
- `temporary_messages`
- `broadcasts`
- `broadcast_recipients`

## Quick start

```bash
cp .env.example .env
# edit BOT_TOKEN, BOT_USERNAME, ADMIN_TELEGRAM_IDS, DATABASE_URL
docker compose up --build
```

Run migrations before polling in a production deployment:

```bash
docker compose run --rm bot alembic upgrade head
```

For local development without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
python -m bot.main
```

## Configuration

All runtime configuration is environment-based and parsed by `pydantic-settings`. See `.env.example` for supported variables:

- `BOT_TOKEN`
- `BOT_USERNAME`
- `DATABASE_URL`
- `ADMIN_TELEGRAM_IDS`
- `FILE_DELETE_AFTER_SECONDS`
- `SCHEDULER_INTERVAL_SECONDS`
- `BROADCAST_RATE_LIMIT_PER_SECOND`
- `LOG_LEVEL`

## Development roadmap

1. Add admin command routers for sponsor, file, premium, and payment management.
2. Add FastAPI admin panel using the existing services and repositories.
3. Add a persistent broadcast runner repository/job for resumable campaigns.
4. Add richer analytics queries for dashboards.
5. Add webhook deployment mode and health checks.
6. Add object-storage integration for cover/proof metadata if needed.
7. Add full integration tests with PostgreSQL Testcontainers.
8. Add CI for Ruff, mypy, pytest, Docker image build, and Alembic migration checks.

## Security notes

- Keep `BOT_TOKEN` secret and never commit `.env`.
- Use private sponsor-channel invite URLs where appropriate.
- Store only Telegram `file_id` values for delivery; Linka does not need to persist file bytes.
- Re-check sponsor and premium access before every delivery.
- Use least-privilege database credentials in production.
