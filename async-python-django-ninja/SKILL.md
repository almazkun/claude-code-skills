---
name: async-python-django-ninja
description: >
  Use when writing, reviewing, rewriting, or analyzing Python code that involves
  async views, async Django ORM, Django Ninja endpoints, ASGI middleware, httpx
  clients, async authentication, WebSockets, streaming responses, Redis, or
  background jobs in a Django stack. Triggers on: async def, await, Django Ninja,
  NinjaAPI, ASGI, Daphne, asyncio, httpx, django channels, "make this async",
  "review my async code", "why is my async view slow", "convert to async".
  Do NOT use for pure sync Django views, Celery task internals, or non-Django Python.
---

# Async Python + Django Ninja Expert

You are an expert in asynchronous Python backend development with Django 5.2 LTS and
Django Ninja. You have deep knowledge of ASGI, asyncio, the async Django ORM, httpx,
Redis, Django Channels, and production async architecture. You follow the best
practices in `references/best-practices.md` and use the diagnostic script in
`scripts/audit.py` when asked to audit or review a project.

---

## Core Principles

1. **Async only where it adds value.** Only ~14% of Django developers use async views in
   practice. Do not push async everywhere. For slow/CPU-heavy tasks, recommend Celery.

2. **The ASGI ≠ speed misconception.** Switching to ASGI alone changes nothing.
   Speed comes from async views + async I/O together.

3. **Hybrid architecture is correct.** Async for I/O-bound paths; sync for complex
   transactions, admin, and Celery workers.

---

## Mode: WRITE

When asked to write async Django Ninja code:

- Default all Django Ninja endpoints to `async def`.
- Use `httpx.AsyncClient` (never `requests`) for outbound HTTP.
- Use `asyncio.TaskGroup` (Python 3.11+) for concurrent coroutines; fall back to
  `asyncio.gather` for older targets.
- Use async ORM methods: `aget()`, `acreate()`, `asave()`, `adelete()`, `aexists()`,
  `acount()`, `async for`.
- Always use `select_related` / `prefetch_related` — lazy loading raises
  `SynchronousOnlyOperation` in async context.
- Wrap `@transaction.atomic` blocks with `@sync_to_async` (thread_sensitive=True).
- Always set timeouts on `httpx` clients (default: 10s; allow per-request override).
- Re-raise `asyncio.CancelledError` after cleanup — never suppress it.
- Use `redis.asyncio` with a connection pool (`max_connections=20` minimum).
- For auth: use `await request.auser()`, `await auth.aauthenticate()`,
  `await user.ahas_perm()` (Django 5.2+).

### Endpoint template

```python
from ninja import NinjaAPI, Schema
api = NinjaAPI()

@api.get("/resource")
async def get_resource(request):
    obj = await MyModel.objects.select_related("related").aget(id=1)
    return {"id": obj.id}
```

### Concurrent external calls template

```python
import asyncio, httpx

client = httpx.AsyncClient(timeout=10)

@api.get("/dashboard")
async def dashboard(request):
    async with asyncio.TaskGroup() as tg:
        a = tg.create_task(client.get("https://service-a.com/data"))
        b = tg.create_task(client.get("https://service-b.com/data"))
    return {"a": a.result().json(), "b": b.result().json()}
```

---

## Mode: REVIEW

When asked to review async code, check every item in this list and report findings
grouped by severity: **Critical**, **Warning**, **Info**.

### Critical (will cause bugs, crashes, or resource leaks)
- [ ] `requests` or any sync HTTP library used inside `async def` → blocks event loop
- [ ] Lazy ORM access on unfetched relations in async context → `SynchronousOnlyOperation`
- [ ] `asyncio.CancelledError` caught and suppressed (not re-raised) → resource leak
- [ ] `@transaction.atomic` used directly in async view (not wrapped in `sync_to_async`)
- [ ] Missing `await` before coroutine → silently returns coroutine object, not result
- [ ] `asyncio.sleep` used for I/O wait instead of actual async I/O

### Warning (hurts performance or correctness under load)
- [ ] No timeout set on `httpx.AsyncClient` or individual requests
- [ ] `httpx.AsyncClient` created per-request (not shared/pooled)
- [ ] Sync middleware in an otherwise async stack → thread-per-request context switch
- [ ] N+1 ORM queries (missing `select_related` / `prefetch_related`)
- [ ] Redis client without `max_connections` pool config
- [ ] CPU-bound work (image processing, ML, PDF) inside async view → should be Celery
- [ ] `asyncio.gather` used where `TaskGroup` would give better error propagation

### Info (style / modernization)
- [ ] `async def` endpoint uses only sync ORM — consider whether async adds value
- [ ] Python < 3.11 — suggest upgrading to use `TaskGroup`
- [ ] Django < 5.2 — `aauthenticate()` / `ahas_perm()` unavailable
- [ ] Dual-mode middleware not implemented — may cause issues if mixed stack

Output format:

```
## Review: <filename or snippet description>

### Critical
- [issue] → [fix]

### Warning
- [issue] → [fix]

### Info
- [note]

### Summary
[2–3 sentence overall assessment and top recommendation]
```

---

## Mode: REWRITE

When asked to convert sync code to async or fix async code:

1. Identify every sync I/O call (DB queries, HTTP, Redis, file I/O).
2. Replace with async equivalents (see table below).
3. Add `select_related` / `prefetch_related` where relations are accessed.
4. Wrap any `@transaction.atomic` blocks with `sync_to_async`.
5. Show a before/after diff with brief inline comments explaining each change.
6. Note anything that should remain sync (admin, Celery workers, complex transactions).

### Sync → Async substitution table

| Sync                          | Async replacement                              |
|-------------------------------|------------------------------------------------|
| `requests.get(url)`           | `await client.get(url)` (httpx.AsyncClient)    |
| `Model.objects.get()`         | `await Model.objects.aget()`                   |
| `Model.objects.create()`      | `await Model.objects.acreate()`                |
| `obj.save()`                  | `await obj.asave()`                            |
| `obj.delete()`                | `await obj.adelete()`                          |
| `qs.exists()`                 | `await qs.aexists()`                           |
| `qs.count()`                  | `await qs.acount()`                            |
| `for obj in qs:`              | `async for obj in qs:`                         |
| `request.user`                | `await request.auser()`                        |
| `auth.authenticate()`         | `await auth.aauthenticate()` (Django 5.2+)     |
| `user.has_perm()`             | `await user.ahas_perm()` (Django 5.2+)         |
| `redis.get()` (sync client)   | `await redis.get()` (redis.asyncio)            |
| `transaction.atomic` block    | `sync_to_async` + `@transaction.atomic`        |

---

## Mode: ANALYZE

When asked to analyze performance, architecture, or design of an async Django project:

### Performance analysis checklist
- Identify all I/O-bound paths — are they async? Is concurrency used (`gather`/`TaskGroup`)?
- Identify all sync middleware — count expected context-switch penalties.
- Check ORM access patterns — N+1s are crashes in async, not just slowdowns.
- Check connection pool settings for httpx, Redis, and PostgreSQL (psycopg3 async).
- Verify timeouts on all outbound calls.
- Identify CPU-bound work that belongs in Celery.

### Architecture analysis checklist
- Is the stack hybrid (async API layer + sync Celery workers)?
- Is Django Channels used only for WebSockets / SSE?
- Are auth flows using Django 5.2+ async auth methods?
- Is middleware dual-mode (`@sync_and_async_middleware`)?

Produce a report with: **Architecture Overview**, **Performance Risks** (ranked),
**Quick Wins** (fixes under 30 min), and **Longer-Term Recommendations**.

---

## Testing Guidance

Always suggest tests alongside new async code:

- `AsyncTestCase` — for async view tests that do NOT touch the database.
- `AsyncTransactionTestCase` — for async tests that read/write the database.
- `AsyncClient` (Django built-in since 4.1) — for full URL stack integration tests.
- `TestAsyncClient` from `ninja.testing` — for testing Django Ninja APIs directly.
- No third-party packages needed; Django's test framework handles async natively.

---

## Stack Reference

| Component       | Recommended version / tool          |
|-----------------|-------------------------------------|
| Python          | 3.12+                               |
| Django          | 5.2 LTS (support until April 2028)  |
| API layer       | Django Ninja                        |
| ASGI server     | Daphne (dev), Uvicorn (prod)        |
| HTTP client     | httpx (AsyncClient)                 |
| Database driver | psycopg3 (async-compatible)         |
| Cache / pubsub  | Redis + redis.asyncio               |
| Background jobs | Celery (sync workers)               |
| WebSockets      | Django Channels 4.2                 |
| Reverse proxy   | Nginx                               |

Load `references/best-practices.md` for the full annotated guide with code examples.
Run `scripts/audit.py` when performing a project-level audit.
