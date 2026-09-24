from src.vector_store import get_vector_store

def retrieve_context(query: str) -> str:
    """Busca casos pasados y reglas oficiales en ChromaDB."""
    # 1. Buscar en tickets pasados
    tickets_db = get_vector_store("historical_tickets")
    similar_tickets = tickets_db.similarity_search(query, k=2)
    
    # 2. Buscar en reglas de negocio
    rules_db = get_vector_store("knowledge_rules")
    relevant_rules = rules_db.similarity_search(query, k=1)
    
    context = "--- REGLAS OFICIALES APLICABLES ---\n"
    for r in relevant_rules:
        context += f"{r.page_content}\n"
        
    context += "\n--- CÓMO SE RESOLVIÓ EN EL PASADO ---\n"
    for t in similar_tickets:
        context += f"{t.page_content}\n"
        
    return context