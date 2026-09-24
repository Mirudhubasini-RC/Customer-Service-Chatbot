"""Unit tests for Schema RAG device configuration (MiniLM on CPU by default)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from schema_rag import DEFAULT_DEVICE, SchemaRAG


def _minimal_docs() -> dict:
    return {
        'database': 'salesdb',
        'notes': [],
        'tables': [
            {
                'table_name': 'products',
                'purpose': 'Product catalog',
                'columns': [
                    {
                        'name': 'product_id',
                        'type': 'INT',
                        'meaning': 'Primary key',
                    }
                ],
                'foreign_keys': [],
                'example_questions': ['Which products exist?'],
            }
        ],
    }


class SchemaRagDeviceTests(unittest.TestCase):
    def test_default_device_is_cpu(self):
        self.assertEqual(DEFAULT_DEVICE, 'cpu')

    def test_sentence_transformer_receives_configured_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs_path = Path(tmp) / 'schema_docs.json'
            cache_path = Path(tmp) / 'schema_embeddings.npz'
            docs_path.write_text(json.dumps(_minimal_docs()), encoding='utf-8')

            # Pre-write a compatible cache so __init__ does not call encode.
            import numpy as np

            np.savez(
                cache_path,
                embeddings=np.zeros((1, 4), dtype=np.float32),
                table_names=np.array(['products'], dtype=object),
                model_name=np.array('sentence-transformers/all-MiniLM-L6-v2'),
            )

            fake_model = MagicMock()
            with patch(
                'sentence_transformers.SentenceTransformer', return_value=fake_model
            ) as st_ctor:
                rag = SchemaRAG(
                    docs_path=docs_path,
                    cache_path=cache_path,
                    device='cpu',
                )
                self.assertEqual(rag.device, 'cpu')
                model = rag._get_model()
                self.assertIs(model, fake_model)
                st_ctor.assert_called_once()
                _args, kwargs = st_ctor.call_args
                self.assertEqual(kwargs.get('device'), 'cpu')

    def test_schema_embed_device_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs_path = Path(tmp) / 'schema_docs.json'
            cache_path = Path(tmp) / 'schema_embeddings.npz'
            docs_path.write_text(json.dumps(_minimal_docs()), encoding='utf-8')
            import numpy as np

            np.savez(
                cache_path,
                embeddings=np.zeros((1, 4), dtype=np.float32),
                table_names=np.array(['products'], dtype=object),
                model_name=np.array('sentence-transformers/all-MiniLM-L6-v2'),
            )

            with patch.dict('os.environ', {'SCHEMA_EMBED_DEVICE': 'cpu'}):
                rag = SchemaRAG(docs_path=docs_path, cache_path=cache_path)
            self.assertEqual(rag.device, 'cpu')


if __name__ == '__main__':
    unittest.main()
