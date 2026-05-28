"""CodeRAGEngine — TF-IDF + cosine similarity retrieval over the code knowledge graph.

Chunks are sourced from the SQLite index (CodeIndexEngine) so no separate file
traversal is needed.  The fitted TF-IDF vectorizer and sparse matrix are
persisted to disk so subsequent queries are near-instant.

scikit-learn and numpy are optional enterprise dependencies.  Every public
method degrades gracefully when they are missing, returning empty results with
a clear installation hint.
"""

from __future__ import annotations

import io
import pickle
import time
from pathlib import Path
from typing import TYPE_CHECKING

from agentra.models import AntiPattern, RAGResult, Severity
from agentra.rag.patterns import AntiPatternLibrary

if TYPE_CHECKING:
    from agentra.index.engine import CodeIndexEngine

_ENTERPRISE_HINT = (
    "scikit-learn and numpy are required for RAG. "
    "Install them with: pip install agentra[enterprise]"
)

_SIMILARITY_THRESHOLD = 0.92  # AP-011 duplicate-chunk threshold


def _require_sklearn():
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import]
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import]
        import numpy as np  # type: ignore[import]
        return TfidfVectorizer, cosine_similarity, np
    except ImportError as e:
        raise ImportError(_ENTERPRISE_HINT) from e


class CodeRAGEngine:
    """
    TF-IDF retrieval engine over code chunks from the knowledge graph.

    Usage::

        rag = CodeRAGEngine(store_path=Path(".agentra"), index_engine=engine)
        rag.build()                          # fit on all indexed chunks
        results = rag.find_similar(code_text, top_k=5)
        antipatterns = rag.detect_antipatterns(code_text, "myfile.py")
    """

    def __init__(self, store_path: Path, index_engine: "CodeIndexEngine") -> None:
        self.store_path = store_path
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._index = index_engine
        self._library = AntiPatternLibrary()

        self._vectorizer_path = store_path / "rag_vectorizer.pkl"
        self._matrix_path = store_path / "rag_matrix.npz"
        self._meta_path = store_path / "rag_meta.pkl"

        self._vectorizer = None
        self._matrix = None
        self._meta: list[tuple[str, int, str]] = []  # (file_path, start_line, symbol_name)

    # ── Persistence ───────────────────────────────────────────────────────

    def _save(self) -> None:
        TfidfVectorizer, _, np = _require_sklearn()
        with open(self._vectorizer_path, "wb") as f:
            pickle.dump(self._vectorizer, f)
        buf = io.BytesIO()
        from scipy.sparse import save_npz  # type: ignore[import]
        save_npz(buf, self._matrix)
        self._matrix_path.write_bytes(buf.getvalue())
        with open(self._meta_path, "wb") as f:
            pickle.dump(self._meta, f)

    def _load(self) -> bool:
        """Try to load from disk. Returns True on success."""
        if not (self._vectorizer_path.exists() and self._matrix_path.exists() and self._meta_path.exists()):
            return False
        try:
            _require_sklearn()  # ensure sklearn/numpy are available
            from scipy.sparse import load_npz  # type: ignore[import]
            with open(self._vectorizer_path, "rb") as f:
                self._vectorizer = pickle.load(f)  # noqa: S301
            self._matrix = load_npz(self._matrix_path)
            with open(self._meta_path, "rb") as f:
                self._meta = pickle.load(f)  # noqa: S301
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── Build / update ────────────────────────────────────────────────────

    def build(self, force: bool = False) -> None:
        """
        Fit the TF-IDF vectorizer over all indexed code chunks.

        Re-fit is always full (TF-IDF requires global IDF statistics).
        For most codebases this completes in under one second.
        """
        try:
            TfidfVectorizer, _, np = _require_sklearn()
        except ImportError:
            return  # degrade gracefully

        if not force and self._load():
            return  # already built and loaded

        chunks = self._index.all_chunks()
        if not chunks:
            return

        texts: list[str] = []
        meta: list[tuple[str, int, str]] = []

        for _cid, file_path, start_line, symbol_name, text in chunks:
            texts.append(text)
            meta.append((file_path, start_line, symbol_name))

        vectorizer = TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b\w[\w.]*\b",  # keep dotted names (e.g. os.path)
            max_features=50_000,
            sublinear_tf=True,
            min_df=1,
        )
        matrix = vectorizer.fit_transform(texts)

        self._vectorizer = vectorizer
        self._matrix = matrix
        self._meta = meta

        try:
            self._save()
        except Exception:  # noqa: BLE001
            pass  # non-fatal; results are still in memory

    def update(self, changed_files: list[Path] | None = None) -> None:
        """
        Rebuild the RAG index.  TF-IDF always re-fits globally because
        document frequencies cannot be updated incrementally, but the
        cost is negligible for typical codebases.
        """
        self.build(force=True)

    # ── Query API ─────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> bool:
        if self._vectorizer is not None:
            return True
        return self._load()

    def find_similar(self, code_text: str, top_k: int = 5) -> list[tuple[str, int, float]]:
        """
        Find the top-k most similar code chunks to *code_text*.

        Returns list of (file_path, start_line, cosine_similarity_score).
        """
        if not code_text.strip():
            return []

        try:
            _, cosine_similarity, np = _require_sklearn()
        except ImportError:
            return []

        if not self._ensure_loaded():
            return []

        try:
            query_vec = self._vectorizer.transform([code_text])
            scores = cosine_similarity(query_vec, self._matrix).flatten()
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                score = float(scores[idx])
                if score < 0.1:
                    break
                file_path, start_line, _symbol = self._meta[idx]
                results.append((file_path, start_line, round(score, 3)))
            return results
        except Exception:  # noqa: BLE001
            return []

    def detect_antipatterns(self, code_text: str, file_path: str, language: str = "python") -> list[AntiPattern]:
        """
        Detect anti-patterns in *code_text* using the pattern library,
        plus duplicate-chunk detection (AP-011) via TF-IDF similarity.
        """
        findings = self._library.scan(code_text, file_path, language)

        # AP-011: duplicate chunk detection
        try:
            _, cosine_similarity, np = _require_sklearn()
            if self._ensure_loaded():
                query_vec = self._vectorizer.transform([code_text])
                scores = cosine_similarity(query_vec, self._matrix).flatten()
                top_score = float(np.max(scores)) if len(scores) > 0 else 0.0
                top_idx = int(np.argmax(scores))
                similar_file, similar_line, _ = self._meta[top_idx] if self._meta else ("", 0, "")
                # Only flag if it's a different location
                if top_score >= _SIMILARITY_THRESHOLD and similar_file != file_path:
                    findings.append(AntiPattern(
                        pattern_id="AP-011",
                        name="duplicate-chunk",
                        severity=Severity.MEDIUM,
                        description=f"High similarity ({top_score:.0%}) with {similar_file}:{similar_line}.",
                        suggestion="Extract duplicated logic into a shared utility function or base class.",
                        file_path=file_path,
                        line=1,
                        context=f"Similar to {similar_file}:{similar_line}",
                    ))
        except Exception:  # noqa: BLE001
            pass

        return findings

    def detect_antipatterns_file(self, path: Path) -> list[AntiPattern]:
        """Convenience wrapper: detect anti-patterns in a file on disk."""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        suffix = path.suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".rs": "rust", ".go": "go", ".java": "java"}
        language = lang_map.get(suffix, "unknown")
        return self.detect_antipatterns(text, str(path), language)

    def suggest_improvements(self, code_text: str) -> list[str]:
        """
        Return actionable improvement suggestions for *code_text*
        based on anti-patterns detected.
        """
        aps = self._library.scan(code_text, "<inline>")
        seen: set[str] = set()
        suggestions: list[str] = []
        for ap in sorted(aps, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.severity.value, 4)):
            if ap.suggestion and ap.suggestion not in seen:
                seen.add(ap.suggestion)
                suggestions.append(f"[{ap.severity.value.upper()}] {ap.name}: {ap.suggestion}")
        return suggestions[:10]

    def project_antipatterns(self) -> list[AntiPattern]:
        """
        Scan all indexed chunks for anti-patterns.
        Returns a deduplicated, severity-sorted list.
        """
        chunks = self._index.all_chunks()
        all_findings: list[AntiPattern] = []
        seen: set[tuple[str, str, int]] = set()

        for _cid, file_path, start_line, _symbol, text in chunks:
            for ap in self._library.scan(text, file_path):
                key = (ap.pattern_id, file_path, ap.line)
                if key not in seen:
                    seen.add(key)
                    all_findings.append(ap)

        # Sort by severity then file
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_findings.sort(key=lambda x: (sev_order.get(x.severity.value, 5), x.file_path, x.line))
        return all_findings

    def top_patterns_summary(self, top_n: int = 3) -> list[str]:
        """
        Return human-readable strings describing the most-used code patterns
        in the project (based on most-frequent symbol names in the index).
        """
        rows = self._index._conn.execute(
            "SELECT name, kind, COUNT(*) as cnt FROM symbols "
            "WHERE kind IN ('function', 'class') "
            "GROUP BY name, kind ORDER BY cnt DESC LIMIT ?",
            (top_n * 2,),
        ).fetchall()

        lines: list[str] = []
        seen_names: set[str] = set()
        for name, kind, cnt in rows:
            if name in seen_names or len(name) <= 2:
                continue
            seen_names.add(name)
            lines.append(f"- `{name}` ({kind}, used {cnt}x across project)")
            if len(lines) >= top_n:
                break
        return lines

    def context_token_cost(self) -> int:
        """Estimated token cost of the RAG patterns block injected into agent files."""
        # patterns block is ~300-500 tokens (small, targeted)
        lines = self.top_patterns_summary(3)
        aps = self.project_antipatterns()[:5]
        text = "\n".join(lines) + "\n".join(ap.description for ap in aps)
        return len(text) // 4
