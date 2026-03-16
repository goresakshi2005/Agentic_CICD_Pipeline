# app/knowledge_base.py
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document        # <-- updated
from app.config import GEMINI_API_KEY
from app.database import SessionLocal, FixKnowledge
import os

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-004", google_api_key=GEMINI_API_KEY)
VECTOR_STORE_PATH = "faiss_index"

def get_vector_store():
    if os.path.exists(VECTOR_STORE_PATH):
        return FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)  # <-- added parameter
    else:
        return FAISS.from_texts(["Placeholder"], embeddings)

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