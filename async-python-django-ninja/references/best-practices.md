# Async Python + Django Ninja — Best Practices Reference

Source: internal best-practices guide (2026). Load this file when the user asks
for detailed code examples, wants to understand *why* a pattern is recommended,
or when reviewing/rewriting a complex async codebase.

---

## When Async Helps vs. Hurts

**Helps:**
- External API calls (concurrent or slow)
- WebSockets / long-polling / streaming
- Real-time notifications
- Redis reads/writes
- High-concurrency APIs with significant I/O wait

**Does NOT help:**
- Simple CRUD apps (use Celery for slow tasks instead)
- CPU-bound work: image processing, ML inference, video → background workers
- Django Admin
- ORM-heavy monoliths with complex transactions

---

## asyncio.TaskGroup vs asyncio.gather

Prefer `TaskGroup` (Python 3.11+) for structured concurrency. If one task raises,
the others are automatically cancelled — unlike `gather` which lets them run on.

```python
# TaskGroup (preferred, Python 3.11+)
async with asyncio.TaskGroup() as tg:
    users_task = tg.create_task(fetch_users())
    posts_task = tg.create_task(fetch_posts())
# Both done here; any exception is re-raised cleanly

# gather (fallback for Python <3.11)
users, posts = await asyncio.gather(fetch_users(), fetch_posts())
```

---

## ASGI Setup

```python
# settings.py
INSTALLED_APPS = [
    "daphne",  # Must be first — overrides runserver with ASGI
    ...
]
ASGI_APPLICATION = "config.asgi.application"

# asgi.py
import os
from django.core.asgi import get_asgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
```

> ASGI alone does NOT make your app faster. You need async views + async I/O.

---

## Async Middleware — The Hidden Performance Trap

Each sync middleware in an async stack forces a context switch (~1ms, holds a thread).
Enough of these eliminate your async advantage entirely.

```python
# Detect context switches — look for "Asynchronous handler adapted for middleware"
LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django.request": {"handlers": ["console"], "level": "DEBUG"}},
}
```

### Dual-mode middleware pattern

```python
from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware

@sync_and_async_middleware
def timing_middleware(get_response):
    if iscoroutinefunction(get_response):
        async def middleware(request):
            return await get_response(request)
    else:
        def middleware(request):
            return get_response(request)
    return middleware
```

---

## Async ORM Cheatsheet

```python
user = await User.objects.aget(id=1)
exists = await User.objects.filter(email="a@b.com").aexists()
count  = await User.objects.acount()
user   = await User.objects.acreate(email="x@y.com")
user.name = "alex"; await user.asave()
await user.adelete()

# Async iteration
async for user in User.objects.filter(active=True).values("id", "email"):
    print(user["email"])

# Always prefetch to avoid SynchronousOnlyOperation
user = await User.objects.select_related("profile").aget(id=1)
book = await Book.objects.prefetch_related("authors").aget(id=1)
```

---

## Async Authentication (Django 5.2+)

```python
user     = await request.auser()
user     = await auth.aauthenticate(request, username="john", password="secret")
can_edit = await user.ahas_perm("myapp.change_article")
```

### Custom async auth backend

```python
from django.contrib.auth.backends import BaseBackend

class ExternalAuthBackend(BaseBackend):
    async def aauthenticate(self, request, username=None, password=None):
        response = await client.post("https://idp.example.com/verify",
                                     json={"username": username, "password": password})
        if response.status_code == 200:
            return await User.objects.aget(username=username)
        return None

    async def ahas_perm(self, user_obj, perm, obj=None):
        return await check_permission_async(user_obj, perm)
```

---

## Transactions (Sync Only — Wrap with sync_to_async)

```python
from asgiref.sync import sync_to_async
from django.db import transaction

@sync_to_async
@transaction.atomic
def create_user_with_profile(data):
    user = User.objects.create(**data)
    Profile.objects.create(user=user)
    return user

@api.post("/users")
async def create(request, payload: dict):
    user = await create_user_with_profile(payload)
    return {"id": user.id}
```

---

## httpx Client — Lifecycle Management

```python
# Shared client (preferred for production)
from contextlib import asynccontextmanager
import httpx

_client: httpx.AsyncClient | None = None

@asynccontextmanager
async def lifespan():
    global _client
    async with httpx.AsyncClient(timeout=10) as client:
        _client = client
        yield
    _client = None

def get_client() -> httpx.AsyncClient:
    assert _client is not None, "HTTP client not initialized"
    return _client
```

---

## Redis with Connection Pool

```python
from redis.asyncio import Redis

redis = Redis(host="localhost", port=6379, decode_responses=True, max_connections=20)

@api.get("/cache")
async def cache(request):
    value = await redis.get("counter")
    return {"value": value}
```

---

## Client Disconnect — CancelledError

```python
@api.get("/long-running")
async def long_task(request):
    try:
        await asyncio.sleep(30)
        return {"status": "done"}
    except asyncio.CancelledError:
        # cleanup here
        raise  # ALWAYS re-raise — never suppress
```

---

## Streaming Responses

```python
from django.http import StreamingHttpResponse

async def stream_data():
    for i in range(5):
        yield f"data: {i}\n\n"
        await asyncio.sleep(1)

@api.get("/stream")
async def stream(request):
    return StreamingHttpResponse(stream_data(), content_type="text/event-stream")
```

---

## Testing

```python
# No-DB async test
from django.test import AsyncTestCase
from ninja.testing import TestAsyncClient
from myapp.api import api

class HealthTests(AsyncTestCase):
    async def test_health(self):
        client = TestAsyncClient(api)
        response = await client.get("/health")
        self.assertEqual(response.status_code, 200)

# DB async test
from django.test import AsyncTransactionTestCase

class UserTests(AsyncTransactionTestCase):
    async def test_create_user(self):
        user = await User.objects.acreate_user(username="x", password="y")
        self.assertEqual(await User.objects.acount(), 1)

# Full stack via URL
from django.test import AsyncClient

class IntegrationTests(AsyncTestCase):
    def setUp(self):
        self.client = AsyncClient()
    async def test_endpoint(self):
        response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
```

Run: `python manage.py test`

---

## Common Mistakes Quick Reference

| Mistake | Fix |
|---|---|
| `requests.get()` in async view | `await httpx_client.get()` |
| ASGI alone = speed | ASGI + async views + async I/O = speed |
| Accessing lazy relation in async | `select_related` / `prefetch_related` |
| Suppressing `CancelledError` | Always re-raise after cleanup |
| `@transaction.atomic` in async view | Wrap with `sync_to_async` |
| Creating `AsyncClient` per-request | Share a pooled client |
| Sync middleware in async stack | Port to dual-mode middleware |
| CPU work in async view | Offload to Celery |
