from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from src.agent import analyze_ticket_with_ai
from src.vector_store import insert_documents
from langchain_core.documents import Document

app = FastAPI(title="Swiss Life AI Support Desk")

class IncomingTicket(BaseModel):
    summary: str
    description: str
    affected_services: Optional[List[str]] = []
    business_entity: Optional[str] = None
    business_critical: Optional[bool] = False

class AdminResolutionFeedback(BaseModel):
    issue_id: str
    issue_key: str
    summary: str
    description: str
    business_entity: Optional[str] = ""
    assigned_team: str
    final_resolution: str
    was_ai_accepted: bool  # True si usó la sugerencia de IA, False si fue manual

@app.post("/api/tickets/analyze")
async def analyze_ticket_endpoint(ticket: IncomingTicket):
    try:
        # Pasa summary y description enriquecidos con entidad
        full_desc = f"{ticket.description} (Entidad: {ticket.business_entity}, Crítico: {ticket.business_critical})"
        recommendation = analyze_ticket_with_ai(ticket.summary, full_desc)
        return {"status": "success", "data": recommendation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tickets/feedback")
async def process_feedback_endpoint(feedback: AdminResolutionFeedback):
    try:
        content = (
            f"Problema validado: {feedback.summary}\n"
            f"Descripción: {feedback.description}\n"
            f"Entidad: {feedback.business_entity}\n"
            f"Resolución definitiva: {feedback.final_resolution}\n"
            f"Equipo responsable: {feedback.assigned_team}"
        )
        
        doc = Document(
            page_content=content,
            metadata={
                "issue_id": feedback.issue_id,
                "issue_key": feedback.issue_key,
                "source": "admin_verified",
                "ai_accepted": str(feedback.was_ai_accepted)
            }
        )
        insert_documents([doc], "historical_tickets")
        return {"status": "success", "message": "Feedback indexado en ChromaDB exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))