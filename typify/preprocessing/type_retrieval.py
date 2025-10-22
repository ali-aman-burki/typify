from whoosh import index
from whoosh.qparser import QueryParser
from pathlib import Path

class TypeRetrievalEngine:
    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        if not self.index_dir.exists():
            raise FileNotFoundError(f"Index directory not found: {self.index_dir}")
        self.ix = index.open_dir(self.index_dir)

    def query(self, context_text: str, topn: int = 4) -> list[str]:
        qp = QueryParser("context", schema=self.ix.schema)
        q = qp.parse(context_text)
        with self.ix.searcher() as searcher:
            results = searcher.search(q, limit=topn)
            return [r["type"] for r in results]
