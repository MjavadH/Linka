<p align="center"><img src="docs/images/Logo.png" alt="Linka"></p>

# Linka

> Open-source Telegram file delivery platform powered by deep links, premium access, sponsor verification, and archive-based storage.

Linka helps you build a complete Telegram file delivery system in minutes.

Upload files through the admin panel, generate deep links, enforce sponsor subscriptions, offer premium access, and automatically deliver files to users — all without storing file bytes outside Telegram.

---

## Why Linka?

Managing file distribution in Telegram can quickly become messy:

* Manual file forwarding
* Expired links
* Sponsor verification
* Premium content access
* Download tracking
* User management

Linka solves these problems with a single self-hosted bot.

---

## Features

### File Delivery

* Deep-link based file delivery
* Telegram-native file storage using `file_id`
* Automatic file deletion after delivery
* Download tracking and analytics
* Archive channel storage

### Content Management

* Movies
* Series
* Episodes
* Multiple quality variants
* Free and premium variants
* Deep-link generation per variant

### Sponsor System

* Multiple sponsor channels
* Required membership verification
* Automatic sponsor expiration
* Date-based campaigns
* Target-member campaigns
* Membership re-checking

### Premium System

* Premium subscription plans
* Premium-only content
* Premium-only quality variants
* Manual subscription management
* Subscription expiration handling

### User Management

* Search users
* Ban and unban users
* Grant and remove premium access
* Direct admin messaging
* User statistics

### Broadcasts

* Send messages to:

  * All users
  * Premium users
  * Free users
* Progress tracking
* Rate limiting
* Cancellation support
* Delivery statistics

### Analytics

* User analytics
* Download analytics
* Sponsor analytics
* Premium analytics
* Top content reports
* Top variant reports

### Administration

* Audit logs
* Health monitoring
* Maintenance tools
* Multi-admin support
* Background job management

---

## Screenshots

### Movie Creation Flow

![Movie Creation](docs/images/movie-creation.gif)

### Analytics

<a href="docs/images/Analytics.jpg">
  <img src="docs/images/Analytics.jpg" alt="Analytics" width="250">
</a>

### Audit Logs

<a href="docs/images/Audit_Logs.jpg">
  <img src="docs/images/Audit_Logs.jpg" alt="Audit Logs" width="250">
</a>

---

## How It Works

```mermaid
flowchart TD
    classDef nodeStyle fill:#f0f9ff,stroke:#0ea5e9,stroke-width:1.5px,color:#0369a1;
    classDef checkStyle fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0369a1;
    classDef SpecialNode fill:#38b6ff,stroke:#0284c7,stroke-width:2px,color:#ffffff;

    subgraph Phase1 [Phase 1: Admin Upload]
        Admin([Admin]) --> Upload[Upload File]
    end

    subgraph Phase2 [Phase 2: Linka Processing]
        Linka[Linka System] --> Archive[Archive Channel]
        Archive --> DeepLink[Deep Link Generated]
    end

    subgraph Phase3 [Phase 3: User Access & Delivery]
        UserOpens[User Opens Link] --> Validation{Access Validation}
        
        Validation -.-> Sponsor[Sponsor Check]
        Validation -.-> Premium[Premium Check]
        Validation -.-> Ban[Ban Check]
        
        Sponsor --> Delivery[File Delivered]
        Premium --> Delivery
        Ban --> Delivery
        
        Delivery --> AutoDel([Auto Deletion])
    end

    Upload --> Linka
    DeepLink --> UserOpens

    %% Force vertical alignment of subgraphs
    Phase1 ~~~ Phase2
    Phase2 ~~~ Phase3

    class Admin,Upload,Archive,DeepLink,UserOpens,Delivery nodeStyle;
    class Validation,Sponsor,Premium,Ban checkStyle;
    class Linka,AutoDel SpecialNode;

    style Phase1 fill:#ffffff,stroke:#e0f2fe,stroke-width:2px,rx:15px,ry:15px,color:#0369a1
    style Phase2 fill:#ffffff,stroke:#e0f2fe,stroke-width:2px,rx:15px,ry:15px,color:#0369a1
    style Phase3 fill:#ffffff,stroke:#e0f2fe,stroke-width:2px,rx:15px,ry:15px,color:#0369a1
```
---

## Quick Start

### Requirements

* Docker
* Docker Compose
* Telegram Bot Token
* PostgreSQL

### Clone Repository

```bash
git clone https://github.com/your-org/linka.git
cd linka
```

### Configure Environment

```bash
cp .env.example .env
```

Edit:

```env
BOT_TOKEN=
BOT_USERNAME=
ARCHIVE_CHAT_ID=
ADMIN_TELEGRAM_IDS=
DATABASE_URL=
```

### Start

```bash
docker compose up --build
```

Run migrations:

```bash
docker compose run --rm bot alembic upgrade head
```

The bot is now ready to use.

---

## Configuration

All configuration is environment-based.

Important settings:

```env
BOT_TOKEN=
BOT_USERNAME=

DATABASE_URL=

ARCHIVE_CHAT_ID=

ADMIN_TELEGRAM_IDS=

FILE_DELETE_AFTER_SECONDS=

SPONSOR_VERIFICATION_INTERVAL_SECONDS=

BROADCAST_RATE_LIMIT_PER_SECOND=
```

See `.env.example` for the full list.

---

## Tech Stack

* Python 3.12+
* Aiogram 3
* PostgreSQL
* SQLAlchemy 2.x
* Alembic
* APScheduler
* Docker
* Docker Compose

---

## Project Structure

```text
src/
├── admin/
├── bot/
├── core/
├── database/
├── handlers/
├── keyboards/
├── middlewares/
├── migrations/
├── models/
├── repositories/
├── scheduler/
├── services/
└── tests/
```

---

## Security

* Never commit `.env`
* Keep your bot token private
* Use private archive channels
* Re-check sponsor membership before delivery
* Use least-privilege database credentials

---

## License

MIT License

See the LICENSE file for details.
