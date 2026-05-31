"""CodeIndexEngine — persistent, incremental code knowledge graph backed by SQLite.

Parses source files into a symbol graph (functions, classes, imports, call edges)
using tree-sitter when available, falling back to Python's built-in ``ast`` module
for Python files and a regex-based chunker for all other languages.

The index lives at ``{index_path}/code_index.db`` and is safe to gitignore.
Only files whose SHA-256 hash has changed are re-parsed, making repeated runs fast.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

from agentra.models import CodeSymbol, IndexReport, SymbolKind

if TYPE_CHECKING:
    pass

# Languages supported by tree-sitter (package name → language name)
_TS_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".cs": "c_sharp",
}

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", "target", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".agentra",
})

_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".whl",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".lock",  # package-lock.json etc are huge and not useful to index
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,
    language     TEXT NOT NULL,
    mtime        REAL NOT NULL,
    last_indexed REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end   INTEGER NOT NULL,
    signature  TEXT NOT NULL DEFAULT '',
    docstring  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS edges (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    src_symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    dst_name      TEXT NOT NULL,
    edge_type     TEXT NOT NULL  -- calls | imports | inherits
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    start_line  INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    symbol_name TEXT NOT NULL DEFAULT '',
    text        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_file  ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_edges_src    ON edges(src_symbol_id);
"""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _detect_language(path: Path) -> str | None:
    return _TS_LANGUAGES.get(path.suffix.lower())


# ── Python AST parser (zero-dependency fallback) ─────────────────────────────

def _parse_python_ast(path: Path) -> list[CodeSymbol]:
    """Extract symbols from a Python file using the built-in ast module."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: list[CodeSymbol] = []
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            sig = _python_func_signature(node, lines)
            doc = ast.get_docstring(node) or ""
            symbols.append(CodeSymbol(
                file_path=str(path),
                name=node.name,
                kind=SymbolKind.METHOD if _is_method(node, tree) else SymbolKind.FUNCTION,
                line_start=node.lineno,
                line_end=end,
                signature=sig,
                docstring=doc[:500],
            ))
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            doc = ast.get_docstring(node) or ""
            bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
            symbols.append(CodeSymbol(
                file_path=str(path),
                name=node.name,
                kind=SymbolKind.CLASS,
                line_start=node.lineno,
                line_end=end,
                signature=f"class {node.name}({bases})",
                docstring=doc[:500],
            ))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            line = node.lineno
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = ", ".join(alias.name for alias in node.names)
                sig = f"from {mod} import {names}"
            else:
                names = ", ".join(alias.name for alias in node.names)
                sig = f"import {names}"
            symbols.append(CodeSymbol(
                file_path=str(path),
                name=sig,
                kind=SymbolKind.IMPORT,
                line_start=line,
                line_end=line,
                signature=sig,
            ))

    return symbols


def _python_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]) -> str:
    """Build a readable signature string for a function node."""
    try:
        return ast.unparse(node).splitlines()[0].rstrip(":")
    except Exception:  # noqa: BLE001
        return f"def {node.name}(...)"


def _extract_python_edges(path: Path, symbols: list[CodeSymbol]) -> list[dict]:
    """Extract call/inherits edges for Python files using the built-in ast module.

    Returns a list of {"src_name": str, "dst_name": str, "edge_type": str} dicts.
    Edge types: "calls", "inherits".
    """
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    # Map line_start → symbol_name for quick lookup of enclosing scope
    # (functions and classes we know about from symbol extraction)
    func_ranges: list[tuple[int, int, str]] = []  # (start, end, name)
    for sym in symbols:
        if sym.kind in (SymbolKind.FUNCTION, SymbolKind.CLASS):
            func_ranges.append((sym.line_start, sym.line_end, sym.name))

    def _enclosing_symbol(lineno: int) -> str | None:
        """Return name of the innermost function/class that contains this line."""
        best: tuple[int, str] | None = None
        for start, end, name in func_ranges:
            if start <= lineno <= end:
                if best is None or start > best[0]:
                    best = (start, name)
        return best[1] if best else None

    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(src: str, dst: str, kind: str) -> None:
        key = (src, dst, kind)
        if key not in seen and src != dst:
            seen.add(key)
            edges.append({"src_name": src, "dst_name": dst, "edge_type": kind})

    for node in ast.walk(tree):
        # Inheritance edges: class Foo(Bar, Baz)
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name):
                    _add(node.name, base.id, "inherits")
                elif isinstance(base, ast.Attribute):
                    _add(node.name, base.attr, "inherits")

        # Call edges: inside a function, detect foo() or self.foo()
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            src = node.name
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        _add(src, child.func.id, "calls")
                    elif isinstance(child.func, ast.Attribute):
                        _add(src, child.func.attr, "calls")

    return edges


def _rebuild_edges_pyan3(
    python_files: list[str],
    name_normpath_to_id: dict[tuple[str, str], int],
    cur: "sqlite3.Cursor",
    seen: set[tuple[int, str]],
) -> int:
    """Use pyan3 for whole-project Python call graph.  Returns edges inserted."""
    try:
        from pyan.analyzer import CallGraphVisitor  # type: ignore[import-untyped]
    except ImportError:
        return 0

    if not python_files:
        return 0

    try:
        v = CallGraphVisitor(python_files)
    except Exception:  # noqa: BLE001
        return 0

    inserted = 0
    for src_node, dst_nodes in v.uses_edges.items():
        filename = getattr(src_node, "filename", None)
        if not filename:
            continue
        src_norm = str(Path(filename).resolve())
        src_id = name_normpath_to_id.get((src_node.name, src_norm))
        if src_id is None:
            continue
        for dst_node in dst_nodes:
            if getattr(dst_node, "namespace", None) is None:
                continue
            pair = (src_id, dst_node.name)
            if pair in seen:
                continue
            seen.add(pair)
            cur.execute(
                "INSERT OR IGNORE INTO edges (src_symbol_id, dst_name, edge_type) VALUES (?,?,?)",
                (src_id, dst_node.name, "calls"),
            )
            inserted += 1
    return inserted


def _rebuild_edges_treesitter(
    files_by_language: dict[str, list[str]],
    name_normpath_to_id: dict[tuple[str, str], int],
    cur: "sqlite3.Cursor",
    seen: set[tuple[int, str]],
) -> int:
    """Extract call edges from non-Python files using tree-sitter call_expression queries.

    Supports JavaScript, TypeScript, Go, Rust, Java, Ruby, C, C++, C#.
    Falls back gracefully if tree-sitter or a grammar is not installed.
    """
    # tree-sitter call_expression query per language
    # Each query captures the callee name from a call expression.
    _TS_CALL_QUERIES: dict[str, str] = {
        "javascript":  "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)])",
        "typescript":  "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)])",
        "tsx":         "(call_expression function: [(identifier) @callee (member_expression property: (property_identifier) @callee)])",
        "go":          "(call_expression function: [(identifier) @callee (selector_expression field: (field_identifier) @callee)])",
        "rust":        "(call_expression function: [(identifier) @callee (field_expression field: (field_identifier) @callee)])",
        "java":        "(method_invocation name: (identifier) @callee)",
        "ruby":        "(call method: (identifier) @callee)",
        "c":           "(call_expression function: (identifier) @callee)",
        "cpp":         "(call_expression function: [(identifier) @callee (field_expression field: (field_identifier) @callee)])",
        "c_sharp":     "(invocation_expression function: [(identifier_name) @callee (member_access_expression name: (identifier_name) @callee)])",
    }

    try:
        import tree_sitter  # noqa: F401
    except ImportError:
        return 0

    inserted = 0
    for language, file_list in files_by_language.items():
        query_src = _TS_CALL_QUERIES.get(language)
        if not query_src:
            continue

        try:
            lang_obj = _load_ts_language(language)
            if lang_obj is None:
                continue
        except Exception:  # noqa: BLE001
            continue

        for filepath in file_list:
            path = Path(filepath)
            try:
                source = path.read_bytes()
                import tree_sitter as ts_mod  # noqa: PLC0415
                parser = ts_mod.Parser()
                parser.language = lang_obj
                tree = parser.parse(source)
            except Exception:  # noqa: BLE001
                continue

            # Build src_symbol_id → name for each symbol in this file
            norm_path = str(path.resolve())
            file_sym_ids = {
                name: sym_id
                for (name, p), sym_id in name_normpath_to_id.items()
                if p == norm_path
            }
            if not file_sym_ids:
                continue

            try:
                query = lang_obj.query(query_src)
                captures = query.captures(tree.root_node)
            except Exception:  # noqa: BLE001
                continue

            # Map byte offset → enclosing symbol name using symbol line ranges from DB
            # For non-Python we use a simpler heuristic: attribute each call to the
            # nearest preceding definition in the file (same approach as per-file ast walker).
            # Load symbol line ranges for this file from DB.
            file_row = cur.connection.execute(
                "SELECT id FROM files WHERE path = ?", (str(path),)
            ).fetchone()
            if file_row is None:
                continue
            sym_ranges = cur.connection.execute(
                "SELECT id, name, line_start, line_end FROM symbols WHERE file_id = ?",
                (file_row[0],),
            ).fetchall()
            # Sort by line_start desc so we can find the nearest enclosing scope
            sym_ranges_sorted = sorted(sym_ranges, key=lambda r: r[2])  # asc by start

            source_lines = source.decode("utf-8", errors="ignore").splitlines()

            for node, tag in (captures if isinstance(captures, list) else captures.items() if hasattr(captures, "items") else []):
                if isinstance(captures, dict):
                    # tree-sitter ≥0.22 returns dict[tag, list[Node]]
                    nodes_for_tag = captures.get("callee", [])
                    callee_nodes = nodes_for_tag if isinstance(nodes_for_tag, list) else [nodes_for_tag]
                else:
                    callee_nodes = [node] if tag == "callee" else []

                for callee_node in callee_nodes:
                    callee_name = source[callee_node.start_byte:callee_node.end_byte].decode("utf-8", errors="ignore")
                    if not callee_name or callee_name.startswith("__"):
                        continue
                    call_line = callee_node.start_point[0] + 1  # 1-based

                    # Find innermost enclosing symbol
                    src_id = None
                    for sym_id, sym_name, line_start, line_end in sym_ranges_sorted:
                        if line_start <= call_line <= (line_end or 999999):
                            src_id = sym_id

                    if src_id is None:
                        continue

                    pair = (src_id, callee_name)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    cur.execute(
                        "INSERT OR IGNORE INTO edges (src_symbol_id, dst_name, edge_type) VALUES (?,?,?)",
                        (src_id, callee_name, "calls"),
                    )
                    inserted += 1

    return inserted


def _rebuild_edges(directory: Path, conn: sqlite3.Connection, skip_dirs: set[str]) -> int:
    """Rebuild the edges table using the best available extractor per language.

    Dispatches:
    - Python  → pyan3 (whole-project, cross-file)
    - JS / TS / Go / Rust / Java / Ruby / C / C++ / C# → tree-sitter call_expression queries
    - Other   → skipped (no call-graph extractor available)

    Clears the existing edges table first.  Falls back gracefully if optional
    dependencies (pyan3, tree-sitter grammars) are not installed.
    """
    # Discover which languages are actually present in this directory
    files_by_language: dict[str, list[str]] = {}
    for f in directory.rglob("*"):
        if any(part in skip_dirs for part in f.parts):
            continue
        if not f.is_file():
            continue
        lang = _detect_language(f)
        if lang:
            files_by_language.setdefault(lang, []).append(str(f))

    if not files_by_language:
        return 0

    # Build shared lookups once
    sym_rows = conn.execute(
        "SELECT s.id, s.name, f.path FROM symbols s JOIN files f ON s.file_id = f.id"
    ).fetchall()
    name_normpath_to_id: dict[tuple[str, str], int] = {}
    for sym_id, sym_name, file_path in sym_rows:
        norm = str(Path(file_path).resolve())
        name_normpath_to_id[(sym_name, norm)] = sym_id

    conn.execute("DELETE FROM edges")

    cur = conn.cursor()
    seen: set[tuple[int, str]] = set()
    total = 0

    # Python: pyan3 (best coverage — whole-project cross-file analysis)
    python_files = files_by_language.get("python", [])
    if python_files:
        total += _rebuild_edges_pyan3(python_files, name_normpath_to_id, cur, seen)

    # All other languages: tree-sitter call_expression queries
    ts_languages = {k: v for k, v in files_by_language.items() if k != "python"}
    if ts_languages:
        total += _rebuild_edges_treesitter(ts_languages, name_normpath_to_id, cur, seen)

    conn.commit()
    return total


def _is_method(node: ast.AST, tree: ast.AST) -> bool:
    """Return True if the function node is inside a class body."""
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            for child in ast.walk(parent):
                if child is node:
                    return True
    return False


# ── tree-sitter parser (optional, multi-language) ────────────────────────────

def _parse_with_treesitter(path: Path, language: str) -> list[CodeSymbol] | None:
    """
    Parse using tree-sitter if the package is installed.
    Returns None if tree-sitter or the language grammar is not available.
    """
    try:
        import tree_sitter  # noqa: F401
    except ImportError:
        return None

    try:
        lang_obj = _load_ts_language(language)
        if lang_obj is None:
            return None
    except Exception:  # noqa: BLE001
        return None

    try:
        from tree_sitter import Language, Parser  # type: ignore[import]
        ts_lang = Language(lang_obj)
        parser = Parser(ts_lang)
        source = path.read_bytes()
        tree = parser.parse(source)
        return _extract_ts_symbols(tree, source, str(path), language)
    except Exception:  # noqa: BLE001
        return None


def _load_ts_language(language: str):
    """Dynamically load a tree-sitter language grammar."""
    module_map = {
        "python":     ("tree_sitter_python",     "language"),
        "javascript": ("tree_sitter_javascript",  "language"),
        "typescript": ("tree_sitter_typescript",  "language_typescript"),
        "tsx":        ("tree_sitter_typescript",  "language_tsx"),
        "rust":       ("tree_sitter_rust",        "language"),
        "go":         ("tree_sitter_go",          "language"),
        "java":       ("tree_sitter_java",        "language"),
        "ruby":       ("tree_sitter_ruby",        "language"),
        "c":          ("tree_sitter_c",           "language"),
        "cpp":        ("tree_sitter_cpp",         "language"),
        "c_sharp":    ("tree_sitter_c_sharp",     "language"),
    }
    if language not in module_map:
        return None
    mod_name, attr = module_map[language]
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)()
    except (ImportError, AttributeError, Exception):  # noqa: BLE001
        return None


def _extract_ts_symbols(tree, source: bytes, file_path: str, language: str) -> list[CodeSymbol]:
    """Walk a tree-sitter CST and extract function/class/import symbols."""
    symbols: list[CodeSymbol] = []
    lines = source.decode("utf-8", errors="ignore").splitlines()

    _FUNC_NODES = {
        "python": {"function_definition", "async_function_definition"},
        "javascript": {"function_declaration", "arrow_function", "function_expression", "method_definition"},
        "typescript": {"function_declaration", "arrow_function", "function_expression", "method_definition"},
        "tsx": {"function_declaration", "arrow_function", "function_expression", "method_definition"},
        "rust": {"function_item"},
        "go": {"function_declaration", "method_declaration"},
        "java": {"method_declaration", "constructor_declaration"},
        "ruby": {"method", "singleton_method"},
        "c": {"function_definition"},
        "cpp": {"function_definition"},
        "c_sharp": {"method_declaration", "constructor_declaration"},
    }
    _CLASS_NODES = {
        "python": {"class_definition"},
        "javascript": {"class_declaration"},
        "typescript": {"class_declaration"},
        "tsx": {"class_declaration"},
        "rust": {"struct_item", "impl_item", "enum_item", "trait_item"},
        "go": {"type_declaration"},
        "java": {"class_declaration", "interface_declaration"},
        "ruby": {"class", "module"},
        "c": {"struct_specifier"},
        "cpp": {"class_specifier", "struct_specifier"},
        "c_sharp": {"class_declaration", "interface_declaration"},
    }
    _IMPORT_NODES = {
        "python": {"import_statement", "import_from_statement"},
        "javascript": {"import_statement"},
        "typescript": {"import_statement"},
        "tsx": {"import_statement"},
        "rust": {"use_declaration"},
        "go": {"import_declaration", "import_spec"},
        "java": {"import_declaration"},
        "ruby": {"require", "require_relative"},
        "c": {"preproc_include"},
        "cpp": {"preproc_include"},
        "c_sharp": {"using_directive"},
    }

    func_nodes = _FUNC_NODES.get(language, set())
    class_nodes = _CLASS_NODES.get(language, set())
    import_nodes = _IMPORT_NODES.get(language, set())

    def _name_from_node(node) -> str:
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return child.text.decode("utf-8", errors="ignore") if child.text else ""
        return node.text.decode("utf-8", errors="ignore")[:60] if node.text else ""

    def _walk(node) -> None:
        ntype = node.type
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        text_preview = "\n".join(lines[start_line - 1: min(start_line + 2, len(lines))])

        if ntype in func_nodes:
            name = _name_from_node(node)
            if name:
                symbols.append(CodeSymbol(
                    file_path=file_path, name=name, kind=SymbolKind.FUNCTION,
                    line_start=start_line, line_end=end_line, signature=text_preview[:120],
                ))
        elif ntype in class_nodes:
            name = _name_from_node(node)
            if name:
                symbols.append(CodeSymbol(
                    file_path=file_path, name=name, kind=SymbolKind.CLASS,
                    line_start=start_line, line_end=end_line, signature=text_preview[:120],
                ))
        elif ntype in import_nodes:
            raw = node.text.decode("utf-8", errors="ignore")[:200] if node.text else ""
            symbols.append(CodeSymbol(
                file_path=file_path, name=raw, kind=SymbolKind.IMPORT,
                line_start=start_line, line_end=end_line, signature=raw,
            ))

        for child in node.children:
            _walk(child)

    _walk(tree.root_node)
    return symbols


# ── Regex chunker (last-resort fallback) ─────────────────────────────────────

def _parse_regex_chunks(path: Path, language: str) -> list[CodeSymbol]:
    """Very basic regex-based symbol extraction for unsupported languages."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    symbols: list[CodeSymbol] = []
    lines = source.splitlines()

    # Generic function/method patterns
    func_patterns = [
        r"^\s*(?:public|private|protected|static|async|export)?\s*(?:function|def|fn|func)\s+(\w+)\s*\(",
        r"^\s*(\w+)\s*[:=]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)",
    ]
    class_pattern = re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?(?:class|struct|interface|enum|trait|impl)\s+(\w+)", re.MULTILINE)

    for i, line in enumerate(lines, 1):
        for pat in func_patterns:
            m = re.match(pat, line)
            if m:
                name = m.group(1)
                symbols.append(CodeSymbol(
                    file_path=str(path), name=name, kind=SymbolKind.FUNCTION,
                    line_start=i, line_end=min(i + 30, len(lines)), signature=line.strip()[:120],
                ))
                break

    for m in class_pattern.finditer(source):
        line_no = source[:m.start()].count("\n") + 1
        symbols.append(CodeSymbol(
            file_path=str(path), name=m.group(1), kind=SymbolKind.CLASS,
            line_start=line_no, line_end=min(line_no + 50, len(lines)), signature=m.group(0).strip()[:120],
        ))

    return symbols


# ── Main engine ───────────────────────────────────────────────────────────────

class CodeIndexEngine:
    """
    Persistent, incremental code knowledge graph.

    Usage::

        engine = CodeIndexEngine(Path(".agentra"))
        report = engine.build(Path("."))         # initial index
        report = engine.update(Path("."))        # re-index changed files only

        symbols = engine.query_symbols("MyClass")
        callers = engine.query_callers("my_function")
        changed = engine.get_changed_files(Path("."))
    """

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.db_path = index_dir / "code_index.db"
        index_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "CodeIndexEngine":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _file_id(self, path: Path) -> int | None:
        row = self._conn.execute("SELECT id FROM files WHERE path = ?", (str(path),)).fetchone()
        return row[0] if row else None

    def _stored_hash(self, path: Path) -> str | None:
        row = self._conn.execute("SELECT content_hash FROM files WHERE path = ?", (str(path),)).fetchone()
        return row[0] if row else None

    def needs_reindex(self, path: Path) -> bool:
        stored = self._stored_hash(path)
        if stored is None:
            return True
        try:
            return _sha256(path) != stored
        except OSError:
            return False

    def _delete_file(self, path: Path) -> None:
        self._conn.execute("DELETE FROM files WHERE path = ?", (str(path),))

    def _extract_chunks(self, path: Path, symbols: list[CodeSymbol]) -> list[dict]:
        """Produce RAG chunks aligned to symbol boundaries."""
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        if not symbols:
            # Fall back to fixed 40-line windows
            chunks = []
            for start in range(0, len(lines), 40):
                end = min(start + 40, len(lines))
                text = "\n".join(lines[start:end])
                chunks.append({"start_line": start + 1, "end_line": end, "symbol_name": "", "text": text})
            return chunks

        chunks = []
        for sym in symbols:
            if sym.kind == SymbolKind.IMPORT:
                continue
            start = max(sym.line_start - 1, 0)
            end = min(sym.line_end, len(lines))
            text = "\n".join(lines[start:end])
            if len(text.strip()) > 20:
                chunks.append({
                    "start_line": sym.line_start,
                    "end_line": sym.line_end,
                    "symbol_name": sym.name,
                    "text": text[:4000],  # cap chunk size
                })
        return chunks

    def _parse(self, path: Path, language: str) -> list[CodeSymbol]:
        """Parse a file, trying tree-sitter → Python ast → regex fallback."""
        if language == "python":
            ts = _parse_with_treesitter(path, language)
            return ts if ts is not None else _parse_python_ast(path)
        ts = _parse_with_treesitter(path, language)
        if ts is not None:
            return ts
        return _parse_regex_chunks(path, language)

    # ── Core index operations ─────────────────────────────────────────────

    def index_file(self, path: Path) -> int:
        """Index a single file. Returns number of symbols inserted."""
        language = _detect_language(path)
        if language is None:
            return 0

        try:
            content_hash = _sha256(path)
            mtime = path.stat().st_mtime
        except OSError:
            return 0

        # Remove stale data for this file
        self._delete_file(path)

        symbols = self._parse(path, language)
        chunks = self._extract_chunks(path, symbols)
        edges = _extract_python_edges(path, symbols) if language == "python" else []

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO files (path, content_hash, language, mtime, last_indexed) VALUES (?,?,?,?,?)",
            (str(path), content_hash, language, mtime, time.time()),
        )
        file_id = cur.lastrowid

        # Build name → row_id map for edge resolution
        name_to_rowid: dict[str, int] = {}
        for sym in symbols:
            cur.execute(
                "INSERT INTO symbols (file_id, name, kind, line_start, line_end, signature, docstring) "
                "VALUES (?,?,?,?,?,?,?)",
                (file_id, sym.name, sym.kind.value, sym.line_start, sym.line_end, sym.signature, sym.docstring),
            )
            name_to_rowid[sym.name] = cur.lastrowid

        for chunk in chunks:
            cur.execute(
                "INSERT INTO chunks (file_id, start_line, end_line, symbol_name, text) VALUES (?,?,?,?,?)",
                (file_id, chunk["start_line"], chunk["end_line"], chunk["symbol_name"], chunk["text"]),
            )

        for edge in edges:
            src_id = name_to_rowid.get(edge["src_name"])
            if src_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO edges (src_symbol_id, dst_name, edge_type) VALUES (?,?,?)",
                    (src_id, edge["dst_name"], edge["edge_type"]),
                )

        self._conn.commit()
        return len(symbols)

    def build(self, directory: Path, force: bool = False, exclude: list[str] | None = None) -> IndexReport:
        """Walk *directory* and index all changed source files."""
        start = time.monotonic()
        skip_dirs = _SKIP_DIRS | set(exclude or [])

        files_indexed = 0
        files_skipped = 0
        symbols_extracted = 0

        for f in directory.rglob("*"):
            if any(part in skip_dirs for part in f.parts):
                continue
            if not f.is_file():
                continue
            if f.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            if _detect_language(f) is None:
                continue
            if f.stat().st_size > 1_000_000:  # skip files > 1MB
                continue

            if force or self.needs_reindex(f):
                count = self.index_file(f)
                symbols_extracted += count
                files_indexed += 1
            else:
                files_skipped += 1

        # After all files are indexed, rebuild edges with the best available extractor
        # per detected language: pyan3 for Python, tree-sitter for everything else.
        _rebuild_edges(directory, self._conn, skip_dirs)

        return IndexReport(
            files_indexed=files_indexed,
            files_skipped=files_skipped,
            symbols_extracted=symbols_extracted,
            duration_seconds=round(time.monotonic() - start, 2),
            incremental=not force,
        )

    def update(self, directory: Path, exclude: list[str] | None = None) -> IndexReport:
        """Incrementally re-index only changed files."""
        return self.build(directory, force=False, exclude=exclude)

    def get_changed_files(self, directory: Path, exclude: list[str] | None = None) -> list[Path]:
        """Return paths of files that need re-indexing (new or hash-changed)."""
        skip_dirs = _SKIP_DIRS | set(exclude or [])
        changed: list[Path] = []
        for f in directory.rglob("*"):
            if any(part in skip_dirs for part in f.parts):
                continue
            if not f.is_file():
                continue
            if f.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            if _detect_language(f) is None:
                continue
            if f.stat().st_size > 1_000_000:
                continue
            if self.needs_reindex(f):
                changed.append(f)
        return changed

    def total_files(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM files").fetchone()
        return row[0] if row else 0

    def total_symbols(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
        return row[0] if row else 0

    def total_chunks(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return row[0] if row else 0

    # ── Query API ─────────────────────────────────────────────────────────

    def query_symbols(self, name: str) -> list[CodeSymbol]:
        rows = self._conn.execute(
            "SELECT f.path, s.name, s.kind, s.line_start, s.line_end, s.signature, s.docstring "
            "FROM symbols s JOIN files f ON s.file_id = f.id WHERE s.name LIKE ? LIMIT 50",
            (f"%{name}%",),
        ).fetchall()
        return [
            CodeSymbol(
                file_path=r[0], name=r[1], kind=SymbolKind(r[2]),
                line_start=r[3], line_end=r[4], signature=r[5], docstring=r[6],
            )
            for r in rows
        ]

    def query_callers(self, symbol_name: str) -> list[CodeSymbol]:
        """Find symbols that have an edge pointing to *symbol_name*."""
        rows = self._conn.execute(
            "SELECT DISTINCT f.path, s.name, s.kind, s.line_start, s.line_end, s.signature, s.docstring "
            "FROM edges e "
            "JOIN symbols s ON e.src_symbol_id = s.id "
            "JOIN files f ON s.file_id = f.id "
            "WHERE e.dst_name = ? LIMIT 50",
            (symbol_name,),
        ).fetchall()
        return [
            CodeSymbol(
                file_path=r[0], name=r[1], kind=SymbolKind(r[2]),
                line_start=r[3], line_end=r[4], signature=r[5], docstring=r[6],
            )
            for r in rows
        ]

    def all_chunks(self) -> list[tuple[int, str, int, str, str]]:
        """Return all chunks: (chunk_id, file_path, start_line, symbol_name, text)."""
        rows = self._conn.execute(
            "SELECT c.id, f.path, c.start_line, c.symbol_name, c.text "
            "FROM chunks c JOIN files f ON c.file_id = f.id"
        ).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def chunks_for_files(self, paths: list[Path]) -> list[tuple[int, str, int, str, str]]:
        """Return chunks belonging to specific files."""
        if not paths:
            return []
        placeholders = ",".join("?" * len(paths))
        rows = self._conn.execute(
            f"SELECT c.id, f.path, c.start_line, c.symbol_name, c.text "
            f"FROM chunks c JOIN files f ON c.file_id = f.id "
            f"WHERE f.path IN ({placeholders})",
            [str(p) for p in paths],
        ).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def file_token_cost(self, path: Path) -> int:
        """Estimate token cost of a file's content (len // 4)."""
        try:
            return len(path.read_bytes()) // 4
        except OSError:
            return 0
