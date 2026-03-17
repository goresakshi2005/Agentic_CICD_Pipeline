# app/knowledge_base.py
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.config import GEMINI_API_KEY
from app.database import SessionLocal, FixKnowledge
import os
import json
import logging

logger = logging.getLogger(__name__)

try:
    embeddings = GoogleGenerativeAIEmbeddings(
        model="text-embedding-004",
        google_api_key=GEMINI_API_KEY
    )
except Exception as e:
    # Defer errors — creating the embeddings client can fail if model unavailable
    embeddings = None
    logger.warning("Could not initialize Google embeddings: %s", e)
VECTOR_STORE_PATH = "faiss_index"

def get_vector_store():
    # Try to use FAISS with the configured embeddings. If embeddings are
    # unavailable (API/model mismatch) fall back to a simple in-memory store
    # that supports the methods we need.
    class InMemoryVectorStore:
        def __init__(self, docs=None):
            self.docs = docs or []

        def add_documents(self, docs):
            for d in docs:
                self.docs.append(d)

        def similarity_search(self, query, k=3):
            # Very simple token-overlap scoring as a fallback
            q_tokens = set(query.lower().split())
            scored = []
            for d in self.docs:
                text = d.page_content if hasattr(d, 'page_content') else str(d)
                score = len(q_tokens.intersection(set(text.lower().split())))
                scored.append((score, d))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [d for s, d in scored[:k]]

        def save_local(self, path):
            os.makedirs(path, exist_ok=True)
            data = [{"page_content": d.page_content, "metadata": getattr(d, "metadata", {})} for d in self.docs]
            with open(os.path.join(path, "in_memory_store.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        @classmethod
        def load_local(cls, path, *args, **kwargs):
            file = os.path.join(path, "in_memory_store.json")
            if not os.path.exists(file):
                return cls()
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            docs = [Document(page_content=item.get("page_content", ""), metadata=item.get("metadata", {})) for item in data]
            return cls(docs=docs)

    # If there is a saved FAISS index, try to load it first
    if os.path.exists(VECTOR_STORE_PATH):
        # Try FAISS load if embeddings are available
        if embeddings is not None:
            try:
                return FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.warning("Failed to load FAISS index, falling back to in-memory store: %s", e)
                try:
                    return InMemoryVectorStore.load_local(VECTOR_STORE_PATH)
                except Exception:
                    return InMemoryVectorStore()
        else:
            try:
                return InMemoryVectorStore.load_local(VECTOR_STORE_PATH)
            except Exception:
                return InMemoryVectorStore()

    # No saved index - create one. Prefer FAISS if embeddings available.
    if embeddings is not None:
        try:
            return FAISS.from_texts(["Placeholder"], embeddings)
        except Exception as e:
            logger.warning("FAISS.from_texts failed, using in-memory fallback: %s", e)
            return InMemoryVectorStore([Document(page_content="Placeholder")])
    else:
        return InMemoryVectorStore([Document(page_content="Placeholder")])

def add_fix_to_knowledge(problem: str, solution: str, success: bool = True):
    vectorstore = get_vector_store()
    doc = Document(page_content=f"Problem: {problem}\nSolution: {solution}", metadata={"success": success})
    vectorstore.add_documents([doc])
    vectorstore.save_local(VECTOR_STORE_PATH)

    db = SessionLocal()
    sig = problem[:255]
    existing = db.query(FixKnowledge).filter_by(problem_signature=sig).first()
    if existing:
        existing.success_count += 1 if success else 0
    else:
        db.add(FixKnowledge(problem_signature=sig, solution=solution, success_count=1 if success else 0))
    db.commit()
    db.close()

def search_similar_problems(problem: str, k: int = 3):
    vectorstore = get_vector_store()
    results = vectorstore.similarity_search(problem, k=k)
    return [doc.page_content for doc in results]