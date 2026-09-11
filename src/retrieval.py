"""TF-IDF retrieval over the reference pool of resolved AppleSupport cases.

The reference pool is built once from data/reference_pool.jsonl, which is
disjoint from the eval pool (see scripts/01_prepare_dataset.py) so retrieval
can never surface a case's own resolution during evaluation.
"""
import json
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import REFERENCE_POOL_PATH


@dataclass
class RetrievedCase:
    case_id: str
    customer_text: str
    brand_reply: str
    similarity: float


class CaseRetriever:
    def __init__(self, pool_path=REFERENCE_POOL_PATH):
        self.cases = []
        with open(pool_path, encoding="utf-8") as f:
            for line in f:
                self.cases.append(json.loads(line))
        corpus = [c["customer_text_clean"] for c in self.cases]
        self.vectorizer = TfidfVectorizer(
            max_features=20000, ngram_range=(1, 2), min_df=2, stop_words="english"
        )
        self.matrix = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query_clean_text: str, k: int = 3) -> list[RetrievedCase]:
        if not query_clean_text.strip():
            return []
        q_vec = self.vectorizer.transform([query_clean_text])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        top_idx = sims.argsort()[::-1][:k]
        results = []
        for i in top_idx:
            if sims[i] <= 0:
                continue
            c = self.cases[i]
            results.append(RetrievedCase(
                case_id=c["case_id"],
                customer_text=c["customer_text"],
                brand_reply=c["brand_reply"],
                similarity=float(sims[i]),
            ))
        return results
