import sys
import os
import json
from langchain_core.documents import Document

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.vector_store import insert_documents

def ingest_knowledge_rules():
    file_path = "data/knowledge_rules.json"
    if not os.path.exists(file_path):
        print("⚠️ No se encontró knowledge_rules.json. Saltando...")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    rules = data.get("rules", data) if isinstance(data, dict) else data
    docs = []
    for rule in rules:
        content = f"Tema: {rule.get('topic', 'General')}\nDirectiva: {rule.get('directive', '')}"
        docs.append(Document(
            page_content=content,
            metadata={"source": "official_kb", "rule_id": str(rule.get("rule_id", "N/A"))}
        ))
        
    insert_documents(docs, "knowledge_rules")
    print(f"✅ {len(docs)} reglas de negocio vectorizadas correctamente.")

def ingest_historical_tickets():
    file_path = "data/tickets_mock.json"
    if not os.path.exists(file_path):
        print("⚠️ No se encontró tickets_mock.json. Saltando...")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Si viene con la clave raíz "tickets", extrae la lista; si no, asume lista directa
    tickets = data.get("tickets", data) if isinstance(data, dict) else data

    if not isinstance(tickets, list):
        raise ValueError("El formato de tickets_mock.json debe contener un array de tickets.")

    docs = []
    for t in tickets:
        summary = t.get("Summary", "")
        desc = t.get("Description", "")
        resolution = t.get("Resolution") or "No documentada formalmente"
        teams = ", ".join(t.get("Service Team(s)", [])) or "Unassigned"
        services = ", ".join(t.get("Affected Business or IT Services", [])) or "None"
        entity = t.get("Business Entity", "Unknown")
        priority = t.get("Priority", "P3")

        # Procesar comentarios estructurados
        raw_comments = t.get("All Comments", [])
        formatted_comments = []
        for c in raw_comments:
            if isinstance(c, dict):
                formatted_comments.append(f"[{c.get('author', 'Anon')}] {c.get('body', '')}")
            elif isinstance(c, str):
                formatted_comments.append(c)
        comments_str = " | ".join(formatted_comments)

        content = (
            f"Problema: {summary}\n"
            f"Descripción: {desc}\n"
            f"Entidad: {entity} | Servicios: {services}\n"
            f"Resolución aplicada: {resolution}\n"
            f"Equipo asignado: {teams}\n"
            f"Historial comentarios: {comments_str}"
        )

        docs.append(Document(
            page_content=content,
            metadata={
                "issue_id": str(t.get("Issue ID", "")),
                "issue_key": str(t.get("Issue Key", "")),
                "priority": priority,
                "entity": entity,
                "source": "historical_ticket"
            }
        ))

    insert_documents(docs, "historical_tickets")
    print(f"✅ {len(docs)} tickets históricos vectorizados correctamente.")

if __name__ == "__main__":
    print("Iniciando pipeline de ingesta offline...")
    ingest_knowledge_rules()
    ingest_historical_tickets()
    print("Pipeline completado. Base de datos vectorial lista.")