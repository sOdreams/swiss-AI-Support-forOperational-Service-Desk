import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DATA_PATH = BASE_DIR / "data" / "processed" / "rag_dataset_balanced.json"
CHROMA_PERSIST_DIR = str(BASE_DIR / "rag" / "chroma_data")

# Inicialización del modelo de embeddings local
embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def ingest_data_to_chroma():
    """Lee el dataset RAG equilibrado y genera los vectores en ChromaDB."""
    if not RAG_DATA_PATH.exists():
        print(f"Error: Dataset no encontrado en {RAG_DATA_PATH}")
        return

    with open(RAG_DATA_PATH, 'r', encoding='utf-8') as f:
        tickets = json.load(f)

    documents = []
    for ticket in tickets:
        # Se concatenan Summary y Description para la búsqueda semántica
        summary = ticket.get("Summary", "")
        description = ticket.get("Description", "")
        page_content = f"Summary: {summary}\nDescription: {description}"
        
        # Guardamos la metadata clave para que el LLM la use en la inferencia
        metadata = {
            "work_type": ticket.get("Work type", "Unknown"),
            "service": ticket.get("Affected Business or IT Services", "Unknown"),
            "team": ticket.get("Service Team(s)", "Unknown"),
            "assignee": ticket.get("Assignee", "Unknown"),
            "resolution_status": ticket.get("Resolution", "Unknown"),
            "comments": " | ".join(ticket.get("All Comments", []))
        }
        
        # Limpiamos las listas en la metadata para evitar errores de ChromaDB
        for key, value in metadata.items():
            if isinstance(value, list):
                metadata[key] = value[0] if value else "Unknown"

        documents.append(Document(page_content=page_content, metadata=metadata))

    print(f"Ingiriendo {len(documents)} tickets en ChromaDB. Este proceso tomará unos minutos...")
    
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings_model,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    print(f"VectorDB creado exitosamente en {CHROMA_PERSIST_DIR}")

def get_top_k_tickets(query: str, k: int = 3):
    """Recupera los k tickets históricos más relevantes basados en similitud semántica."""
    vector_store = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=embeddings_model
    )
    
    return vector_store.similarity_search(query, k=k)

if __name__ == "__main__":
    ingest_data_to_chroma()