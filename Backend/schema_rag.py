"""
Schema RAG for RetailAsk — retrieve relevant MySQL schema docs for NL→SQL.

This is Schema RAG only (database schema retrieval). It is NOT Business Graph RAG.
Retrieval uses local sentence-transformer embeddings + cosine similarity (no keyword matching).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger('retail-agent')

DEFAULT_DOCS_PATH = Path(__file__).resolve().parent / 'schema_kb' / 'schema_docs.json'
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent / 'schema_kb' / 'schema_embeddings.npz'
DEFAULT_MODEL = os.getenv('SCHEMA_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')


def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and each row of matrix."""
    q = query_vec.astype(np.float32)
    m = matrix.astype(np.float32)
    q_norm = np.linalg.norm(q) + 1e-12
    m_norm = np.linalg.norm(m, axis=1) + 1e-12
    return (m @ q) / (m_norm * q_norm)


def _doc_to_embed_text(table: dict[str, Any]) -> str:
    """Flatten a schema document into text for embedding."""
    col_bits = []
    for col in table.get('columns') or []:
        col_bits.append(
            f"{col['name']} ({col.get('type', '')}): {col.get('meaning', '')}"
        )
    fk_bits = []
    for fk in table.get('foreign_keys') or []:
        fk_bits.append(
            f"{fk['column']} -> {fk['references_table']}.{fk['references_column']}"
        )
    examples = table.get('example_questions') or []
    return (
        f"Table: {table['table_name']}\n"
        f"Purpose: {table.get('purpose', '')}\n"
        f"Columns: {'; '.join(col_bits)}\n"
        f"Foreign keys: {'; '.join(fk_bits) if fk_bits else 'none'}\n"
        f"Example questions: {' | '.join(examples)}"
    )


def _format_table_for_llm(table: dict[str, Any]) -> str:
    """Concise schema block for the SQL LLM."""
    lines = [
        f"Table: {table['table_name']}",
        f"Purpose: {table.get('purpose', '')}",
        'Columns:',
    ]
    for col in table.get('columns') or []:
        lines.append(
            f"  - {col['name']} {col.get('type', '')} — {col.get('meaning', '')}"
        )
    fks = table.get('foreign_keys') or []
    if fks:
        lines.append('Foreign keys:')
        for fk in fks:
            lines.append(
                f"  - {table['table_name']}.{fk['column']} → "
                f"{fk['references_table']}.{fk['references_column']}"
            )
    return '\n'.join(lines)


class SchemaRAG:
    """Semantic Schema RAG retriever over RetailAsk table documentation."""

    def __init__(
        self,
        docs_path: str | Path | None = None,
        cache_path: str | Path | None = None,
        model_name: str | None = None,
        top_k: int | None = None,
    ):
        self.docs_path = Path(docs_path or os.getenv('SCHEMA_DOCS_PATH', DEFAULT_DOCS_PATH))
        self.cache_path = Path(cache_path or os.getenv('SCHEMA_EMBED_CACHE', DEFAULT_CACHE_PATH))
        self.model_name = model_name or DEFAULT_MODEL
        self.top_k = int(top_k or os.getenv('SCHEMA_RAG_TOP_K', '3'))

        self._model = None
        self._tables: list[dict[str, Any]] = []
        self._notes: list[str] = []
        self._db_name = os.getenv('DB_NAME', 'salesdb')
        self._embeddings: np.ndarray | None = None
        self._table_names: list[str] = []
        self._fk_outbound: dict[str, set[str]] = {}
        self._fk_inbound: dict[str, set[str]] = {}
        self._lookup_tables: set[str] = set()

        self._load_docs()
        self._build_fk_adjacency()
        self._ensure_embeddings()

    def _load_docs(self) -> None:
        if not self.docs_path.is_file():
            raise FileNotFoundError(f'Schema docs not found: {self.docs_path}')
        with self.docs_path.open(encoding='utf-8') as f:
            payload = json.load(f)
        self._db_name = payload.get('database') or self._db_name
        self._notes = list(payload.get('notes') or [])
        self._tables = list(payload.get('tables') or [])
        if not self._tables:
            raise ValueError(f'No tables found in {self.docs_path}')
        self._table_names = [t['table_name'] for t in self._tables]
        self._table_by_name = {t['table_name']: t for t in self._tables}

    def _build_fk_adjacency(self) -> None:
        """
        Directed FK edges:
          outbound: table → tables it references (JOIN parents)
          inbound:  table → tables that reference it (fact/child tables)
        """
        outbound: dict[str, set[str]] = {name: set() for name in self._table_names}
        inbound: dict[str, set[str]] = {name: set() for name in self._table_names}
        for table in self._tables:
            src = table['table_name']
            for fk in table.get('foreign_keys') or []:
                dst = fk['references_table']
                if dst in outbound:
                    outbound[src].add(dst)
                    inbound[dst].add(src)
        self._fk_outbound = outbound
        self._fk_inbound = inbound
        # Lookup / dimension tables (no outbound FKs): brands, categories, issues
        self._lookup_tables = {name for name, outs in outbound.items() if not outs}

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info('Schema RAG loading embedding model | %s', self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _ensure_embeddings(self) -> None:
        texts = [_doc_to_embed_text(t) for t in self._tables]
        cache_ok = False
        if self.cache_path.is_file():
            try:
                cached = np.load(self.cache_path, allow_pickle=True)
                names = list(cached['table_names'])
                model = str(cached['model_name'])
                if names == self._table_names and model == self.model_name:
                    self._embeddings = cached['embeddings'].astype(np.float32)
                    cache_ok = True
                    logger.info(
                        'Schema RAG loaded embedding cache | tables=%s | path=%s',
                        len(self._table_names),
                        self.cache_path,
                    )
            except Exception as exc:
                logger.warning('Schema RAG cache load failed, rebuilding | %s', exc)

        if not cache_ok:
            model = self._get_model()
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            self._embeddings = np.asarray(vectors, dtype=np.float32)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(
                self.cache_path,
                embeddings=self._embeddings,
                table_names=np.array(self._table_names, dtype=object),
                model_name=np.array(self.model_name),
            )
            logger.info(
                'Schema RAG built embeddings | tables=%s | cached=%s',
                len(self._table_names),
                self.cache_path,
            )

    def _embed_query(self, question: str) -> np.ndarray:
        model = self._get_model()
        vec = model.encode([question], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vec[0], dtype=np.float32)

    def _expand_related(self, seed_tables: list[str]) -> list[str]:
        """
        Expand retrieved tables for usable SQL JOINs:
        1) Outbound FKs: sales → products; customer_feedback → products + issues
        2) For lookup seeds (brands/categories/issues): inbound FKs so fact tables
           are included (issues → customer_feedback; brands → products)
        3) Re-run outbound expansion once more for any newly added tables
        """
        expanded = list(seed_tables)
        seen = set(seed_tables)

        def add(name: str) -> None:
            if name not in seen:
                seen.add(name)
                expanded.append(name)

        for name in list(expanded):
            for neighbor in sorted(self._fk_outbound.get(name, ())):
                add(neighbor)

        for name in list(expanded):
            if name in self._lookup_tables:
                for neighbor in sorted(self._fk_inbound.get(name, ())):
                    add(neighbor)

        for name in list(expanded):
            for neighbor in sorted(self._fk_outbound.get(name, ())):
                add(neighbor)

        return expanded

    def build_schema_context(self, table_names: list[str]) -> str:
        blocks = [
            f'MySQL database: {self._db_name}',
            '',
            'Retrieved schema (Schema RAG — only tables relevant to the question):',
            '',
        ]
        for name in table_names:
            table = self._table_by_name.get(name)
            if not table:
                continue
            blocks.append(_format_table_for_llm(table))
            blocks.append('')
        if self._notes:
            blocks.append('Notes:')
            for note in self._notes:
                blocks.append(f'- {note}')
        return '\n'.join(blocks).strip()

    def retrieve(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        """
        Semantic Schema RAG retrieve.

        Returns:
          {
            question, retrieved_tables, scores, expanded_tables,
            schema_context, hits: [{table, score, expanded}]
          }
        """
        if not question or not str(question).strip():
            raise ValueError('question must be a non-empty string')

        k = int(top_k or self.top_k)
        k = max(1, min(k, len(self._tables)))

        query_vec = self._embed_query(question.strip())
        scores = _cosine_similarity(query_vec, self._embeddings)
        ranked_idx = np.argsort(-scores)[:k]

        hits = []
        seed_tables = []
        for idx in ranked_idx:
            name = self._table_names[int(idx)]
            score = float(scores[int(idx)])
            seed_tables.append(name)
            hits.append({'table': name, 'score': round(score, 4), 'via': 'semantic'})

        expanded_tables = self._expand_related(seed_tables)
        for name in expanded_tables:
            if name not in seed_tables:
                hits.append({'table': name, 'score': None, 'via': 'fk_expansion'})

        schema_context = self.build_schema_context(expanded_tables)

        logger.info('Schema RAG question | %s', question)
        logger.info(
            'Schema RAG semantic hits | %s',
            ', '.join(f"{h['table']}={h['score']}" for h in hits if h['via'] == 'semantic'),
        )
        logger.info('Schema RAG expanded tables | %s', ', '.join(expanded_tables))
        logger.info('Schema RAG context sent to Qwen |\n%s', schema_context)

        return {
            'question': question,
            'retrieved_tables': seed_tables,
            'scores': {
                h['table']: h['score'] for h in hits if h['via'] == 'semantic'
            },
            'expanded_tables': expanded_tables,
            'hits': hits,
            'schema_context': schema_context,
        }


_schema_rag_singleton: SchemaRAG | None = None


def get_schema_rag() -> SchemaRAG:
    """Lazy singleton used by the Flask app."""
    global _schema_rag_singleton
    if _schema_rag_singleton is None:
        _schema_rag_singleton = SchemaRAG()
    return _schema_rag_singleton
