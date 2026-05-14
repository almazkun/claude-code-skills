#!/usr/bin/env python3
"""
async-python-django-ninja audit script
--------------------------------
Run from the root of a Django project to detect common async anti-patterns.

Usage:
    python scripts/audit.py [path]   # default path: current directory

Output: a Markdown report grouped by severity (Critical / Warning / Info).
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    severity: str  # "critical" | "warning" | "info"
    file: str
    line: int
    message: str
    fix: str


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity, file, line, message, fix):
        self.findings.append(Finding(severity, file, line, message, fix))

    def render(self) -> str:
        if not self.findings:
            return "## Audit Result\n\nNo issues found. ✅\n"

        sections = {"critical": [], "warning": [], "info": []}
        for f in self.findings:
            sections[f.severity].append(f)

        lines = ["# Async Django Ninja — Audit Report\n"]
        emojis = {"critical": "🔴", "warning": "🟡", "info": "🔵"}

        for level in ("critical", "warning", "info"):
            items = sections[level]
            if not items:
                continue
            lines.append(f"## {emojis[level]} {level.capitalize()} ({len(items)})\n")
            for item in items:
                lines.append(f"- **{item.file}:{item.line}** — {item.message}")
                lines.append(f"  - Fix: {item.fix}")
            lines.append("")

        total = len(self.findings)
        crit = len(sections["critical"])
        lines.append(
            f"---\n**Total findings: {total}** "
            f"({crit} critical, {len(sections['warning'])} warning, "
            f"{len(sections['info'])} info)"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# AST-based checkers
# ---------------------------------------------------------------------------

SYNC_HTTP_MODULES = {"requests", "urllib", "urllib3", "httplib2"}
SYNC_REDIS_ATTRS = {"StrictRedis", "Redis"}  # from redis (not redis.asyncio)


class AsyncAuditor(ast.NodeVisitor):
    """Walk one file's AST and collect findings."""

    def __init__(self, filepath: str, report: AuditReport):
        self.filepath = filepath
        self.report = report
        self._inside_async_func: list[bool] = []
        self._imports: dict[str, str] = {}  # local_name → module

    # ------------------------------------------------------------------
    # Import tracking
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = f"{module}.{alias.name}"
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Function scope tracking
    # ------------------------------------------------------------------

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._inside_async_func.append(True)
        self.generic_visit(node)
        self._inside_async_func.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._inside_async_func.append(False)
        self.generic_visit(node)
        self._inside_async_func.pop()

    @property
    def _in_async(self) -> bool:
        return bool(self._inside_async_func) and self._inside_async_func[-1]

    # ------------------------------------------------------------------
    # Call checkers
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call):
        if self._in_async:
            self._check_sync_http(node)
            self._check_sync_redis(node)
            self._check_direct_atomic(node)
        self._check_cancelled_error_suppressed(node)
        self.generic_visit(node)

    def _check_sync_http(self, node: ast.Call):
        """Detect requests.get / requests.post etc. inside async def."""
        func = node.func
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                module_alias = func.value.id
                resolved = self._imports.get(module_alias, module_alias)
                if any(resolved.startswith(m) for m in SYNC_HTTP_MODULES):
                    self.report.add(
                        "critical",
                        self.filepath,
                        node.lineno,
                        f"Sync HTTP call `{module_alias}.{func.attr}()` inside async def blocks the event loop.",
                        "Replace with `await httpx_client.get/post/...()` using a shared `httpx.AsyncClient`.",
                    )

    def _check_sync_redis(self, node: ast.Call):
        """Detect Redis() from the sync redis package (not redis.asyncio) in async context."""
        func = node.func
        if isinstance(func, ast.Name) and func.id in SYNC_REDIS_ATTRS:
            resolved = self._imports.get(func.id, "")
            if resolved.startswith("redis.") and "asyncio" not in resolved:
                self.report.add(
                    "warning",
                    self.filepath,
                    node.lineno,
                    f"Sync Redis client `{func.id}` used inside async def.",
                    "Use `from redis.asyncio import Redis` instead.",
                )

    def _check_direct_atomic(self, node: ast.Call):
        """Detect transaction.atomic() used as a call (not decorator) in async def."""
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "atomic":
            if isinstance(func.value, ast.Name) and func.value.id == "transaction":
                self.report.add(
                    "critical",
                    self.filepath,
                    node.lineno,
                    "`transaction.atomic()` called directly inside async def.",
                    "Wrap the atomic block in a sync function decorated with `@sync_to_async`.",
                )

    def _check_cancelled_error_suppressed(self, node: ast.Call):
        """Detect bare `pass` in except CancelledError blocks (walk parent manually)."""
        # This is handled via visit_ExceptHandler below.
        pass

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Flag except CancelledError: pass  (swallowed)."""
        if node.type:
            name = ""
            if isinstance(node.type, ast.Attribute):
                name = (
                    f"{node.type.value.id}.{node.type.attr}"
                    if isinstance(node.type.value, ast.Name)
                    else ""
                )
            elif isinstance(node.type, ast.Name):
                name = node.type.id

            if "CancelledError" in name:
                # Check if body is only `pass` or only assignments (no `raise`)
                has_raise = any(
                    isinstance(s, ast.Raise)
                    for s in ast.walk(ast.Module(body=node.body, type_ignores=[]))
                )
                if not has_raise:
                    self.report.add(
                        "critical",
                        self.filepath,
                        node.lineno,
                        "`asyncio.CancelledError` is caught but never re-raised — causes resource leaks.",
                        "Add `raise` at the end of the except block after any cleanup.",
                    )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Decorator checkers
    # ------------------------------------------------------------------

    def visit_AsyncFunctionDef2(self, node):
        """Check for @transaction.atomic directly on an async def."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute) and decorator.attr == "atomic":
                self.report.add(
                    "critical",
                    self.filepath,
                    node.lineno,
                    f"`@transaction.atomic` applied directly to async def `{node.name}`.",
                    "Remove the decorator and wrap the body in a `@sync_to_async` helper function.",
                )


# ---------------------------------------------------------------------------
# Settings / config checkers (regex-based, no AST needed)
# ---------------------------------------------------------------------------

SYNC_MIDDLEWARE_PATTERNS = [
    "whitenoise.middleware",
    "corsheaders.middleware",
    "debug_toolbar.middleware",
    "rollbar.contrib.django",
]


def audit_settings_file(filepath: str, report: AuditReport):
    text = Path(filepath).read_text(errors="replace")
    for pattern in SYNC_MIDDLEWARE_PATTERNS:
        for i, line in enumerate(text.splitlines(), 1):
            if pattern in line and not line.strip().startswith("#"):
                report.add(
                    "warning",
                    filepath,
                    i,
                    f"Potentially sync-only middleware `{pattern}` in MIDDLEWARE list.",
                    "Verify the middleware supports async; if not, write a dual-mode wrapper "
                    "using `@sync_and_async_middleware`.",
                )

    if "WSGI_APPLICATION" in text and "ASGI_APPLICATION" not in text:
        report.add(
            "info",
            filepath,
            0,
            "Only `WSGI_APPLICATION` found — project is running in WSGI mode.",
            "Set `ASGI_APPLICATION` and add `daphne` to `INSTALLED_APPS` to enable async.",
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def audit_project(root: Path) -> AuditReport:
    report = AuditReport()

    for py_file in root.rglob("*.py"):
        # Skip migrations, venv, __pycache__
        parts = py_file.parts
        if any(
            p in parts
            for p in ("migrations", "venv", ".venv", "__pycache__", "node_modules")
        ):
            continue

        source = py_file.read_text(errors="replace")
        rel = str(py_file.relative_to(root))

        # AST audit
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            report.add(
                "info",
                rel,
                e.lineno or 0,
                f"SyntaxError — skipped: {e.msg}",
                "Fix syntax error.",
            )
            continue

        auditor = AsyncAuditor(rel, report)
        auditor.visit(tree)

        # Settings file heuristic
        if py_file.name in ("settings.py", "settings_local.py", "base.py"):
            audit_settings_file(str(py_file), report)

    return report


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(1)

    print(f"Auditing: {root.resolve()}\n")
    report = audit_project(root)
    print(report.render())

    critical_count = sum(1 for f in report.findings if f.severity == "critical")
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == "__main__":
    main()
