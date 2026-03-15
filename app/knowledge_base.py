from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema import Document
from app.config import GEMINI_API_KEY
import os

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)

VECTOR_STORE_PATH = "faiss_index"

def get_vector_store():
    if os.path.exists(VECTOR_STORE_PATH):
        return FAISS.load_local(VECTOR_STORE_PATH, embeddings)
    else:
        return FAISS.from_texts(["initial"], embeddings)  # placeholder

def add_to_knowledge_base(problem: str, solution: str):
    vectorstore = get_vector_store()
    doc = Document(page_content=f"Problem: {problem}\nSolution: {solution}", metadata={})
    vectorstore.add_documents([doc])
    vectorstore.save_local(VECTOR_STORE_PATH)

def search_similar_problems(problem: str, k: int = 3):
    vectorstore = get_vector_store()
    results = vectorstore.similarity_search(problem, k=k)
    return [doc.page_content for doc in results]