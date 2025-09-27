# GenovationTech FastAPI Backend

A production-ready FastAPI backend featuring async PostgreSQL (SQLAlchemy), Redis-backed caching and rate limiting, Celery for background processing, OTP-first authentication with JWT, and modular services for chatroom and messaging.

## Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Robust relational database with SQLAlchemy ORM
- **Redis** - In-memory data store for caching and message queuing
- **Celery** - Distributed task queue for background jobs
- **JWT Authentication** - Secure token-based authentication
- **Pydantic** - Data validation using Python type annotations

## Project Structure

```
.
├── Dockerfile
├── alembic.ini
├── requirements.txt
├── README.md
├── .env (local env vars)
└── app/
    ├── main.py                # FastAPI app entrypoint (includes routers and middleware)
    ├── main_enhanced.py       # Alternate app bootstrap (example/experimental)
    ├── config.py              # Settings via pydantic-settings
    ├── database.py            # Async SQLAlchemy engine/session
    ├── redis_client.py        # Redis client helpers
    ├── celery_app.py          # Celery config
    ├── models/                # ORM models: User, Chatroom, Message
    ├── routes/                # API routers: auth, user, chatroom
    ├── schemas/               # Pydantic schemas (requests/responses)
    ├── services/              # Business logic (user/chatroom/message/otp/usage/cache)
    ├── middlewares/           # Auth, rate limit, logging, error handler
    ├── utils/                 # JWT, auth helpers, queue utils, etc.
    └── workers/               # Celery tasks
```

## Setup

1. **Clone and navigate to the project:**
   ```bash
   cd /path/to/project
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual configuration
   ```

5. **Setup PostgreSQL database:**
   - Create a PostgreSQL database
   - Update `DATABASE_URL` in your `.env` file

6. **Setup Redis:**
   - Install and start Redis server
   - Update `REDIS_URL` in your `.env` file if needed

## Running the Application

1. Start the FastAPI server
   ```bash
   uvicorn app.main:app --reload
   ```

2. Start Celery worker (in a separate terminal)
   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```

3. Start Celery Beat (optional)
   ```bash
   celery -A app.celery_app beat --loglevel=info
   ```

## API Endpoints (summary)

- `/` GET — Root
- `/health` GET — Health check

Auth (`app/routes/auth.py`)
- `/auth/signup` POST — Register user
- `/auth/send-otp` POST — Send OTP to mobile
- `/auth/verify-otp` POST — Verify OTP and return access token
- `/auth/forgot-password` POST — Send OTP for password reset
- `/auth/change-password` POST — Change password (auth required)

Users (`app/routes/users.py`)
- `/user/me` GET — Current user profile (auth required)
- `/user/me` PUT — Update profile (auth required)

Chatrooms (`app/routes/chatrooms.py`)
- `/chatroom/` POST — Create chatroom (auth)
- `/chatroom/` GET — List my chatrooms with pagination (auth)
- `/chatroom/{chatroom_id}` GET — Chatroom details with messages page (auth)
- `/chatroom/{chatroom_id}` PUT — Update chatroom (auth)
- `/chatroom/{chatroom_id}` DELETE — Soft delete chatroom (auth)
- `/chatroom/{chatroom_id}/message` POST — Send a message (auth)
- `/chatroom/{chatroom_id}/messages` GET — List messages with optional relations (auth)
- `/chatroom/{chatroom_id}/messages/{message_id}` GET — Get a message plus AI response (auth)
- `/chatroom/{chatroom_id}/messages/{message_id}/status` GET — Poll for AI response (auth)
- `/chatroom/{chatroom_id}/conversation` GET — Conversation as user/AI pairs (auth)
- `/chatroom/{chatroom_id}/conversation-tree` GET — Conversation tree (auth)
- `/chatroom/task-status/{task_id}` GET — Queue/Task health/status

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

Configured via `app/config.py` using pydantic-settings. Define these in your `.env`:

App
- `APP_NAME`
- `DEBUG` (true/false)
- `HOST` (e.g., 0.0.0.0)
- `PORT` (e.g., 8000)
- `VERSION` (e.g., 0.1.0)

Database
- `DATABASE_URL` (e.g., postgresql+asyncpg://user:pass@host:5432/dbname)

Redis
- `REDIS_URL` (e.g., redis://localhost:6379/0)

JWT
- `SECRET_KEY`
- `ALGORITHM` (e.g., HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_MINUTES`

Celery
- `CELERY_BROKER_URL` (e.g., redis://localhost:6379/1)
- `CELERY_RESULT_BACKEND` (e.g., redis://localhost:6379/2)

Replicate/LLM
- `REPLICATE_API_TOKEN`

OTP
- `OTP_LENGTH`
- `OTP_EXPIRE_MINUTES`
- `OTP_MAX_ATTEMPTS`
- `OTP_RATE_LIMIT_PER_HOUR`

Rate Limits
- `BASIC_TIER_DAILY_LIMIT`
- `PRO_TIER_DAILY_LIMIT`

Cache
- `CACHE_TTL_CHATROOMS`
- `CACHE_TTL_USER_DATA`

Security
- `CORS_ORIGINS` (comma-separated)
- `ALLOWED_HOSTS` (comma-separated)

Pagination
- `DEFAULT_PAGE_SIZE`
- `MAX_PAGE_SIZE`

Message
- `MAX_MESSAGE_LENGTH`
- `CONVERSATION_CONTEXT_LIMIT`

## Development

The project follows a clean architecture pattern with separate layers for:
- **Models**: Database entities
- **Schemas**: Request/response validation
- **Services**: Business logic
- **Routes**: API endpoints
- **Workers**: Background tasks
- **Middlewares**: Custom middleware components
- **Utils**: Utility functions

### Notable Behaviors
- **Auth Middleware** (`app/middlewares/auth_middleware.py`): extracts and verifies JWT, checks Redis token blacklist, and enforces active user.
- **Rate Limiting** (`RateLimitMiddleware`): simple IP-based throttle using Redis counters, with configurable window.
- **Caching** (`app/services/cache_service.py`): Redis-backed cache for user chatroom lists with TTL.
- **Messaging and LLM**: user messages are stored and queued for AI response via `LlamaService` and message services; task status exposed via `/chatroom/task-status/{task_id}`.

## Testing

Run the test suite with pytest and view a coverage summary.

1. Install test dependencies (already included in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```

2. Run tests with coverage:
   ```bash
   pytest
   ```

   The command uses the configuration in `pytest.ini` to generate a coverage report for the `app/` package and display a term-missing summary.

3. Run a specific test module or test:
   ```bash
   pytest tests/test_users.py::test_get_and_update_me_success -q
   ```

Notes:
- Tests use an in-memory SQLite database and mock Redis, so no external services are required.
- JWT verification is enabled; tests generate tokens via helpers in `tests/conftest.py`.
