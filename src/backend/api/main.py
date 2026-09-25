import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from rag.vector_store import get_top_k_tickets
from llm.triage import run_llm_triage
from rules.priority import calculate_priority
from rag.vector_store import add_feedback_to_store 


app = FastAPI(title="Ticket Triage API - Service Desk Copilot")

# CORS configuration required by the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INPUT SCHEMAS ---
class TicketRequest(BaseModel):
    ticket_id: str
    ticket: dict

class BatchTicketRequest(BaseModel):
    tickets: List[TicketRequest]

class HumanFeedbackRequest(BaseModel):
    ticket_id: str
    original_ticket: dict
    ai_analysis: dict
    solution_feedback: List[dict]
    selected_solution_id: Optional[str] = None
    real_solution: Optional[str] = None
    selected_affected_area: Optional[str] = None
    source: str = "human_in_the_loop_rag_feedback"

# --- OUTPUT SCHEMAS (Frontend Contract) ---
class Prediction(BaseModel):
    value: str
    confidence: Optional[float] = None  # Will be null if omitted, UI won't show the %
    method: Optional[str] = None
    reason: Optional[str] = None

class AIAnalysis(BaseModel):
    work_type: Prediction
    affected_service: Prediction
    service_team: Prediction
    assignee: Prediction
    urgency: Prediction
    impact: Prediction
    priority: Prediction
    resolution_status: Prediction

class RecommendedSolution(BaseModel):
    id: str
    title: str
    description: str
    confidence: Optional[float] = None

class AffectedArea(BaseModel):
    id: str
    label: str
    confidence: Optional[float] = None

class TriageResponse(BaseModel):
    ticket_id: str
    status: str
    analysis: AIAnalysis
    recommended_solutions: List[RecommendedSolution]
    affected_areas: List[AffectedArea]
    evidence: List[dict] = []

# --- ENDPOINTS ---

@app.post("/triage", response_model=TriageResponse)
def triage_ticket(payload: TicketRequest):
    ticket_data = payload.ticket
    summary = ticket_data.get("Summary", "")
    description = ticket_data.get("Description", "")
    reported_service = ticket_data.get("Affected Business or IT Services", [""])[0] if isinstance(ticket_data.get("Affected Business or IT Services"), list) else ticket_data.get("Affected Business or IT Services", "")

    # 1. RAG Retrieval (No fake confidence/similarity)
    query = f"Summary: {summary}\nDescription: {description}"
    try:
        retrieved_docs = get_top_k_tickets(query, k=3)
        historical_context = ""
        evidence_list = []
        for idx, doc in enumerate(retrieved_docs):
            historical_context += f"--- SIMILAR TICKET {idx+1} ---\n{doc.page_content}\n"
            historical_context += f"Historical Solution: {doc.metadata.get('resolution_status')} - {doc.metadata.get('comments')}\n\n"
            
            evidence_list.append({
                "ticket_id": f"historical-{idx+1}",
                "summary": doc.page_content[:50] + "...",
                "resolution_excerpt": doc.metadata.get('comments', '')[:100]
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG Error: {str(e)}")

    # 2. LLM Inference
    try:
        llm_result = run_llm_triage(
            summary=summary,
            description=description,
            reported_service=reported_service,
            historical_context=historical_context
        )
    except Exception as e:
        return {"ticket_id": payload.ticket_id, "status": "error", "error": {"code": "TRIAGE_FAILED", "message": str(e)}}

    # 3. Deterministic Rules (Pure matrix calculation)
    final_priority = calculate_priority(llm_result.urgency, llm_result.impact)

    # 4. Qualitative structuring with DEBUG in Priority reason
    debug_priority_reason = f"MATRIX DEBUG: Urgency '{llm_result.urgency}' + Impact '{llm_result.impact}' = Priority '{final_priority}'"
    
    analysis = AIAnalysis(
        work_type=Prediction(value=llm_result.work_type, method="llm_inference", reason="Classification based on narrative context"),
        affected_service=Prediction(value=llm_result.service, method="llm_inference", reason="Mapped against the ITIL service catalogue"),
        service_team=Prediction(value=llm_result.team, method="llm_inference", reason="Assignment based on the affected primary service"),
        assignee=Prediction(value=llm_result.assignee, method="llm_inference"),
        urgency=Prediction(value=llm_result.urgency, method="llm_inference", reason="Deduced from reporter's tone, SLA, and blockers"),
        impact=Prediction(value=llm_result.impact, method="llm_inference", reason="Evaluated based on entity and impact volume"),
        priority=Prediction(value=final_priority, method="urgency_impact_matrix", reason=debug_priority_reason),
        resolution_status=Prediction(value=llm_result.resolution_status, method="llm_inference")
    )

    # 5. Generation of 3 solutions without hardcoded confidence
    solutions = []
    
    # Option 1: LLM Reasoning
    solutions.append(
        RecommendedSolution(
            id="solution_1",
            title="Synthesized Resolution (AI)",
            description=llm_result.resolution_text
        )
    )

    # Option 2 and 3: Real historical resolutions extracted from ChromaDB
    for idx, doc in enumerate(retrieved_docs[:2]):
        hist_comments = doc.metadata.get('comments', 'No detailed record in the original ticket.')
        solutions.append(
            RecommendedSolution(
                id=f"solution_{idx+2}",
                title=f"Historical Alternative (Ticket {doc.metadata.get('issue_key', 'Legacy')})",
                description=hist_comments[:400] 
            )
        )
        
    # If RAG retrieves less than 2 tickets, force a standard fallback solution
    while len(solutions) < 3:
        solutions.append(
            RecommendedSolution(
                id=f"solution_{len(solutions)+1}",
                title="Standard Escalation",
                description="Gather logs, application traces, and escalate the ticket to the Level 2 specialist team."
            )
        )

    # 6. Generation of 3 Affected Areas (Primary service + dependencies)
    areas = [
        AffectedArea(id="area_1", label=llm_result.service),
        AffectedArea(id="area_2", label=f"Dependencies of {llm_result.team}"),
        AffectedArea(id="area_3", label="Downstream Operations / Business Users")
    ]

    return TriageResponse(
        ticket_id=payload.ticket_id,
        status="success",
        analysis=analysis,
        recommended_solutions=solutions,
        affected_areas=areas,
        evidence=evidence_list
    )

@app.post("/triage/batch")
def triage_batch(payload: BatchTicketRequest):
    """Processes an array of tickets, ensuring one error doesn't invalidate the batch."""
    results = []
    for req in payload.tickets:
        try:
            result = triage_ticket(req)
            results.append(result)
        except Exception as e:
            results.append({
                "ticket_id": req.ticket_id,
                "status": "error",
                "error": {"code": "TRIAGE_FAILED", "message": str(e)}
            })
    return {"results": results}

@app.post("/feedback/rag")
def submit_feedback(payload: HumanFeedbackRequest):
    """Receives human validation and the chosen solution to move the ticket to Processed."""
    print(f"Feedback received for ticket {payload.ticket_id}. Chosen solution: {payload.selected_solution_id}")
    return {"status": "success", "message": "Feedback successfully registered"}

@app.post("/retrieval/search")
async def retrieval_search(request: Request):
    """Evidence endpoint for the secondary panel, without simulated metrics."""
    try:
        payload = await request.json()
        search_text = payload.get("query") or payload.get("search_string") or payload.get("text") or str(payload)
        retrieved_docs = get_top_k_tickets(search_text, k=50)
        
        evidence_list = []
        for idx, doc in enumerate(retrieved_docs):
            evidence_list.append({
                "ticket_id": f"historical-search-{idx+1}",
                "summary": doc.page_content[:150] + "...",
                "resolution_excerpt": doc.metadata.get('comments', 'No resolution available')[:200]
            })
            
        return evidence_list
    except Exception as e:
        print(f"Error parsing manual search: {e}")
        return []



@app.post("/feedback/rag")
def submit_feedback(payload: HumanFeedbackRequest):
    """Recibe la validación humana y retroalimenta la base de datos vectorial."""
    
    # 1. Determinar cuál fue la solución final real
    final_solution_text = ""
    if payload.real_solution:
        # El humano escribió una solución completamente nueva
        final_solution_text = payload.real_solution
    else:
        # El humano eligió una de las recomendaciones de la IA
        for feedback in payload.solution_feedback:
            if feedback.get("solution_id") == payload.selected_solution_id:
                # Buscamos el texto de esa solución en el análisis que nos devuelve el frontend
                # (Asumiendo que el frontend pasa el texto o podemos deducirlo)
                final_solution_text = "Solución validada a partir de recomendación IA." 
                break
    
    # 2. Construir los datos del ticket para re-entrenamiento
    summary = payload.original_ticket.get("Summary", "")
    description = payload.original_ticket.get("Description", "")
    
    # 3. Guardar en ChromaDB
    try:
        add_feedback_to_store(
            ticket_summary=summary,
            ticket_description=description,
            final_resolution=final_solution_text,
            metadata={"source_ticket": payload.ticket_id}
        )
        return {"status": "success", "message": "Feedback registrado y VectorDB actualizado."}
    except Exception as e:
        print(f"Error actualizando VectorDB: {e}")
        # Devolvemos success al frontend para no bloquear la UI, pero logueamos el error
        return {"status": "success", "message": "Feedback recibido, pero hubo un error en la vectorización."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)