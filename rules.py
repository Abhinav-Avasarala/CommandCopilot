"""
rules.py — Error-to-fix lookup table using regex patterns.

When the consumer receives an error, it runs it through these rules in order.
The first matching pattern wins and returns the fix string.
"""

import re

# Each rule is a tuple of (regex_pattern, fix_function)
# The fix_function receives the regex match object so it can use capture groups
RULES = [
    # ── Python Errors ──────────────────────────────────────────────────────────
    (
        r"ModuleNotFoundError: No module named '(.+)'",
        lambda m: f"pip install {m.group(1).split('.')[0]}"
    ),
    (
        r"ImportError: No module named '(.+)'",
        lambda m: f"pip install {m.group(1).split('.')[0]}"
    ),
    (
        r"ImportError: cannot import name '(.+)' from '(.+)'",
        lambda m: f"'{m.group(1)}' doesn't exist in '{m.group(2)}' — check the module version or spelling"
    ),
    (
        r"SyntaxError: invalid syntax",
        lambda _: "Syntax error — check for missing colons, brackets, or quotes near the line shown above"
    ),
    (
        r"NameError: name '(.+)' is not defined",
        lambda m: f"'{m.group(1)}' is not defined — check spelling or make sure it is imported/assigned first"
    ),
    (
        r"TypeError: (.+) takes (\d+) positional argument",
        lambda m: f"Wrong number of arguments passed to {m.group(1)} — expected {m.group(2)}"
    ),
    (
        r"TypeError: '(.+)' object is not (iterable|subscriptable|callable)",
        lambda m: f"Cannot use '{m.group(1)}' as {m.group(2)} — check the variable type"
    ),
    (
        r"FileNotFoundError: .* '(.+)'",
        lambda m: f"File '{m.group(1)}' not found — check the path is correct and the file exists"
    ),
    (
        r"PermissionError: .* '(.+)'",
        lambda m: f"Permission denied on '{m.group(1)}' — try: chmod +x {m.group(1)}"
    ),
    (
        r"IndexError: list index out of range",
        lambda _: "List index out of range — check your loop bounds or print len(list) to debug"
    ),
    (
        r"KeyError: '(.+)'",
        lambda m: f"Key '{m.group(1)}' not in dictionary — use .get('{m.group(1)}') to safely access it"
    ),
    (
        r"AttributeError: '(.+)' object has no attribute '(.+)'",
        lambda m: f"'{m.group(1)}' has no attribute '{m.group(2)}' — check spelling or object type"
    ),
    (
        r"ZeroDivisionError",
        lambda _: "Division by zero — add a check: if denominator != 0 before dividing"
    ),
    (
        r"RecursionError: maximum recursion depth exceeded",
        lambda _: "Infinite recursion detected — check your base case or add a depth limit"
    ),
    (
        r"MemoryError",
        lambda _: "Out of memory — try processing data in chunks or reducing batch size"
    ),

    # ── Node.js / npm Errors ───────────────────────────────────────────────────
    (
        r"Cannot find module '(.+)'",
        lambda m: f"npm install {m.group(1)}"
    ),
    (
        r"EADDRINUSE.*:(\d+)",
        lambda m: f"Port {m.group(1)} is already in use — run: lsof -ti:{m.group(1)} | xargs kill"
    ),
    (
        r"ENOENT: no such file or directory, open '(.+)'",
        lambda m: f"File '{m.group(1)}' not found — check the path is correct"
    ),
    (
        r"EACCES: permission denied",
        lambda _: "Permission denied — try: sudo npm install or fix directory ownership"
    ),

    # ── General Shell / System Errors ─────────────────────────────────────────
    (
        r"command not found: (.+)",
        lambda m: f"'{m.group(1)}' is not installed — install it or check: which {m.group(1)}"
    ),
    (
        r"No such file or directory",
        lambda _: "File or directory not found — double-check the path"
    ),
    (
        r"connection refused",
        lambda _: "Connection refused — check if the target service is running on the expected port"
    ),
    (
        r"timed? ?out",
        lambda _: "Request timed out — check network connectivity or increase the timeout value"
    ),
    (
        r"out of memory|OOM",
        lambda _: "Out of memory — reduce data size, increase memory allocation, or process in batches"
    ),
    (
        r"disk quota exceeded",
        lambda _: "Disk quota exceeded — free up space with: du -sh * | sort -rh | head"
    ),
    (
        r"Killed",
        lambda _: "Process was killed — likely OOM. Check memory usage with: free -h"
    ),
]


def get_fix(error_text: str) -> str:
    """
    Run error_text through each rule in order.
    Return the fix string from the first matching rule.

    If no regex rule matches, falls back to a local Phi-2 LLM (llm_fallback.py).
    The LLM is optional — if not installed or model file is missing, returns the
    default "no fix found" message instead of crashing.
    """
    for pattern, fix_fn in RULES:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            return fix_fn(match)

    # ── LLM fallback ──────────────────────────────────────────────────────────
    # Regex found no match. Try the local Phi-2 model before giving up.
    try:
        from llm_fallback import get_llm_fix
        llm_fix = get_llm_fix(error_text)
        if llm_fix:
            return f"[LLM] {llm_fix}"
    except Exception:
        pass  # LLM unavailable for any reason — fall through gracefully

    return "No known fix found. Try searching the exact error message on Stack Overflow or the project's GitHub issues."


def get_error_type(error_text: str) -> str:
    """Extract the main error class name from the error text."""
    match = re.search(
        r'([A-Za-z]+Error|[A-Za-z]+Exception|EADDRINUSE|ENOENT|EACCES)',
        error_text
    )
    return match.group(1) if match else "UnknownError"
