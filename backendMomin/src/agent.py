from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List
from src.retriever import retrieve_context
from src.config import settings

class AIRecommendation(BaseModel):
    category: str = Field(description="Incident o Service Request")
    priority: str = Field(description="P1, P2, P3 o P4 según impacto y reglas Swiss Life")
    assigned_team: str = Field(description="Equipo sugerido: IAM, Application Support, etc.")
    affected_services: List[str] = Field(description="Servicios afectados identificados")
    proposed_solution: str = Field(description="Pasos técnicos concretos recomendados para el admin")
    impact_analysis: str = Field(description="Explicación del impacto sobre el negocio")

def analyze_ticket_with_ai(ticket_summary: str, ticket_description: str) -> dict:
    # Conectamos con el cerebro de Azure OpenAI
    llm = AzureChatOpenAI(
        azure_deployment=settings.CHAT_MODEL_DEPLOYMENT_NAME,
        openai_api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        temperature=0.1
    )
    
    query = f"{ticket_summary} - {ticket_description}"
    context = retrieve_context(query)
    
    parser = JsonOutputParser(pydantic_object=AIRecommendation)
    
    system_prompt = """
    Eres un analista experto del Service Desk de Swiss Life.
    Analiza el nuevo ticket usando ESTRICTAMENTE las reglas oficiales y el historial proporcionado.
    
    CONTEXTO DE LA BASE DE DATOS (Historial y Reglas):
    {context}
    
    Devuelve ÚNICAMENTE un JSON válido con tu análisis. No incluyas texto fuera del JSON.
    {format_instructions}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Resumen: {summary}\nDescripción: {description}")
    ])
    
    chain = prompt | llm | parser
    
    return chain.invoke({
        "context": context, 
        "summary": ticket_summary, 
        "description": ticket_description,
        "format_instructions": parser.get_format_instructions()
    })