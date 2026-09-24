from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from typing import List
from src.config import settings

def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Motor local: Descarga un modelo ultraligero a tu PC y vectoriza sin internet.
    """
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vector_store(collection_name: str) -> Chroma:
    return Chroma(
        persist_directory=settings.CHROMA_PERSIST_DIRECTORY,
        embedding_function=get_embedding_model(),
        collection_name=collection_name
    )

def insert_documents(documents: List[Document], collection_name: str):
    if not documents:
        return
    db = get_vector_store(collection_name)
    db.add_documents(documents)