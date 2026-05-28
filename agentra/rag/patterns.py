"""Anti-pattern library — pure-regex and structural code smell detection.

12 built-in patterns covering god classes, long methods, mutable defaults,
bare excepts, wildcard imports, magic numbers, and more.  Zero external
dependencies — works on raw source text.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentra.models import AntiPattern, Severity

# ── Pattern definitions ───────────────────────────────────────────────────────

# Each entry: (pattern_id, name, severity, description, suggestion, regex_or_None)
# regex_or_None=None means structural detection (handled in code below)
_PATTERN_DEFS: list[tuple[str, str, Severity, str, str, str | None]] = [
    (
        "AP-001",
        "god-class",
        Severity.HIGH,
        "Class body exceeds 300 lines — consider splitting into smaller focused classes.",
        "Apply Single Responsibility Principle: extract cohesive groups of methods into separate classes.",
        None,  # structural
    ),
    (
        "AP-002",
        "long-method",
        Severity.MEDIUM,
        "Function/method body exceeds 50 lines — hard to test and reason about.",
        "Extract sub-steps into well-named helper functions. Aim for functions that fit on one screen.",
        None,  # structural
    ),
    (
        "AP-003",
        "deep-nesting",
        Severity.MEDIUM,
        "Code nesting exceeds 4 levels — increases cognitive complexity.",
        "Use early returns (guard clauses), extract nested blocks into functions, or use pattern matching.",
        None,  # structural
    ),
    (
        "AP-004",
        "magic-number",
        Severity.LOW,
        "Numeric literal used inline — intent is unclear.",
        "Replace bare numbers with named constants (UPPER_CASE) at module level.",
        r"(?<!['\"\w\-])\b(?!0\b|1\b|2\b|100\b)(\d{2,})\b(?!['\"\w])",
    ),
    (
        "AP-005",
        "mutable-default-arg",
        Severity.HIGH,
        "Mutable default argument — shared across all calls, causes subtle bugs.",
        "Replace `def f(x=[])` with `def f(x=None)` and set `x = x if x is not None else []` inside.",
        r"def\s+\w+\s*\([^)]*=\s*(\[\s*\]|\{\s*\}|\(\s*\))[^)]*\)",
    ),
    (
        "AP-006",
        "bare-except",
        Severity.HIGH,
        "Bare `except:` catches everything including SystemExit and KeyboardInterrupt.",
        "Catch specific exception types. At minimum use `except Exception:` and log the error.",
        r"^\s*except\s*:\s*$",
    ),
    (
        "AP-007",
        "wildcard-import",
        Severity.MEDIUM,
        "Wildcard import pollutes the namespace and hides dependencies.",
        "Import only what you use: `from module import SpecificClass, specific_function`.",
        r"from\s+[\w.]+\s+import\s+\*",
    ),
    (
        "AP-008",
        "commented-code",
        Severity.LOW,
        "Large block of commented-out code — dead code creates noise and confusion.",
        "Delete commented-out code; use version control (git) to retrieve it if needed.",
        None,  # structural: 5+ consecutive comment lines
    ),
    (
        "AP-009",
        "todo-density",
        Severity.LOW,
        "High TODO/FIXME density — more than 5 unresolved markers in a single file.",
        "Resolve or convert TODOs to tracked issues. Unresolved markers indicate incomplete work.",
        None,  # structural: counted per-file
    ),
    (
        "AP-010",
        "missing-type-hints",
        Severity.LOW,
        "Public function has no type annotations — harder to understand and refactor.",
        "Add type hints: `def my_func(x: int, y: str) -> bool:`. Use `mypy` to validate.",
        r"^\s*def\s+(?!_)(\w+)\s*\((?![^)]*:\s*\w)",
    ),
    (
        "AP-011",
        "duplicate-chunk",
        Severity.MEDIUM,
        "Code chunk has high similarity (>92%) with another chunk in the project — possible duplication.",
        "Extract the duplicated logic into a shared utility function or base class.",
        None,  # handled by RAG cosine similarity
    ),
    (
        "AP-012",
        "global-mutation",
        Severity.HIGH,
        "Assignment to a module-level variable inside a function — hidden side effect.",
        "Pass values as arguments and return results. Use class state instead of globals.",
        r"^\s+global\s+\w+",
    ),
]


class AntiPatternLibrary:
    """Detect code smells and anti-patterns in source text."""

    def __init__(self) -> None:
        # Compile regex patterns once
        self._regex_patterns: list[tuple[str, str, Severity, str, str, re.Pattern]] = []
        for pid, name, sev, desc, sugg, pat in _PATTERN_DEFS:
            if pat is not None:
                self._regex_patterns.append((pid, name, sev, desc, sugg, re.compile(pat, re.MULTILINE)))

    def scan(self, code_text: str, file_path: str, language: str = "python") -> list[AntiPattern]:
        """Scan *code_text* for anti-patterns. Returns a list of findings."""
        findings: list[AntiPattern] = []
        lines = code_text.splitlines()

        # ── Regex-based patterns ──────────────────────────────────────────
        for pid, name, sev, desc, sugg, pattern in self._regex_patterns:
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    findings.append(AntiPattern(
                        pattern_id=pid, name=name, severity=sev,
                        description=desc, suggestion=sugg,
                        file_path=file_path, line=i, context=line.strip()[:200],
                    ))

        # ── Structural patterns ───────────────────────────────────────────

        # AP-001 god-class: class body > 300 lines
        findings.extend(self._detect_god_classes(lines, file_path))

        # AP-002 long-method: function body > 50 lines
        findings.extend(self._detect_long_methods(lines, file_path, language))

        # AP-003 deep-nesting: > 4 indent levels
        findings.extend(self._detect_deep_nesting(lines, file_path))

        # AP-008 commented-code: 5+ consecutive comment lines
        findings.extend(self._detect_commented_code(lines, file_path))

        # AP-009 todo-density: > 5 TODOs per file
        todo_count = sum(1 for ln in lines if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", ln, re.IGNORECASE))
        if todo_count > 5:
            findings.append(AntiPattern(
                pattern_id="AP-009", name="todo-density", severity=Severity.LOW,
                description=f"File contains {todo_count} TODO/FIXME markers.",
                suggestion="Resolve or file issues for unresolved TODOs.",
                file_path=file_path, line=1, context=f"{todo_count} markers found",
            ))

        # Deduplicate by (pattern_id, line)
        seen: set[tuple[str, int]] = set()
        deduped: list[AntiPattern] = []
        for ap in findings:
            key = (ap.pattern_id, ap.line)
            if key not in seen:
                seen.add(key)
                deduped.append(ap)

        return deduped

    def scan_file(self, path: Path) -> list[AntiPattern]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        suffix = path.suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".rs": "rust", ".go": "go", ".java": "java"}
        language = lang_map.get(suffix, "unknown")
        return self.scan(text, str(path), language)

    # ── Structural helpers ────────────────────────────────────────────────

    def _detect_god_classes(self, lines: list[str], file_path: str) -> list[AntiPattern]:
        results = []
        class_start: int | None = None
        class_name = ""
        class_pattern = re.compile(r"^class\s+(\w+)")
        for i, line in enumerate(lines, 1):
            m = class_pattern.match(line)
            if m:
                if class_start is not None:
                    size = i - class_start
                    if size > 300:
                        results.append(AntiPattern(
                            pattern_id="AP-001", name="god-class", severity=Severity.HIGH,
                            description=f"Class '{class_name}' has {size} lines.",
                            suggestion="Apply Single Responsibility Principle: split into smaller classes.",
                            file_path=file_path, line=class_start,
                            context=f"class {class_name} ({size} lines)",
                        ))
                class_start = i
                class_name = m.group(1)
        if class_start is not None:
            size = len(lines) - class_start + 1
            if size > 300:
                results.append(AntiPattern(
                    pattern_id="AP-001", name="god-class", severity=Severity.HIGH,
                    description=f"Class '{class_name}' has {size} lines.",
                    suggestion="Apply Single Responsibility Principle: split into smaller classes.",
                    file_path=file_path, line=class_start,
                    context=f"class {class_name} ({size} lines)",
                ))
        return results

    def _detect_long_methods(self, lines: list[str], file_path: str, language: str) -> list[AntiPattern]:
        results = []
        func_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(")
        func_start: int | None = None
        func_name = ""
        base_indent = 0
        for i, line in enumerate(lines, 1):
            m = func_pattern.match(line)
            if m:
                if func_start is not None:
                    size = i - func_start
                    if size > 50:
                        results.append(AntiPattern(
                            pattern_id="AP-002", name="long-method", severity=Severity.MEDIUM,
                            description=f"Function '{func_name}' has {size} lines.",
                            suggestion="Extract sub-steps into well-named helper functions.",
                            file_path=file_path, line=func_start,
                            context=f"def {func_name} ({size} lines)",
                        ))
                func_start = i
                func_name = m.group(2)
                base_indent = len(line) - len(line.lstrip())
        if func_start is not None:
            size = len(lines) - func_start + 1
            if size > 50:
                results.append(AntiPattern(
                    pattern_id="AP-002", name="long-method", severity=Severity.MEDIUM,
                    description=f"Function '{func_name}' has {size} lines.",
                    suggestion="Extract sub-steps into well-named helper functions.",
                    file_path=file_path, line=func_start,
                    context=f"def {func_name} ({size} lines)",
                ))
        return results

    def _detect_deep_nesting(self, lines: list[str], file_path: str) -> list[AntiPattern]:
        results = []
        reported: set[int] = set()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if not stripped:
                continue
            indent = len(line) - len(stripped)
            # Python: 4 spaces per level → 4 levels = 16 spaces
            level = indent // 4
            if level >= 5 and i not in reported:
                results.append(AntiPattern(
                    pattern_id="AP-003", name="deep-nesting", severity=Severity.MEDIUM,
                    description=f"Nesting depth of {level} levels detected.",
                    suggestion="Use early returns, extract nested blocks into functions.",
                    file_path=file_path, line=i, context=line.strip()[:120],
                ))
                reported.add(i)
        return results[:10]  # cap at 10 per file

    def _detect_commented_code(self, lines: list[str], file_path: str) -> list[AntiPattern]:
        results = []
        comment_run = 0
        run_start = 0
        comment_re = re.compile(r"^\s*#")
        for i, line in enumerate(lines, 1):
            if comment_re.match(line) and len(line.strip()) > 1:
                if comment_run == 0:
                    run_start = i
                comment_run += 1
            else:
                if comment_run >= 5:
                    results.append(AntiPattern(
                        pattern_id="AP-008", name="commented-code", severity=Severity.LOW,
                        description=f"{comment_run} consecutive commented lines starting at line {run_start}.",
                        suggestion="Delete commented-out code; use git history to retrieve it.",
                        file_path=file_path, line=run_start, context=f"{comment_run} comment lines",
                    ))
                comment_run = 0
        if comment_run >= 5:
            results.append(AntiPattern(
                pattern_id="AP-008", name="commented-code", severity=Severity.LOW,
                description=f"{comment_run} consecutive commented lines starting at line {run_start}.",
                suggestion="Delete commented-out code; use git history to retrieve it.",
                file_path=file_path, line=run_start, context=f"{comment_run} comment lines",
            ))
        return results
