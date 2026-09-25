import os
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

# Cargar variables de entorno (API keys de Azure)
load_dotenv()

class TriageResult(BaseModel):
    work_type: str = Field(description="Must be strictly 'Incident' or 'Service Request'")
    service: str = Field(description="The actual affected Business or IT Service")
    team: str = Field(description="The Service Team responsible for the service")
    assignee: str = Field(description="The specific agent email assigned to resolve this")
    urgency: str = Field(description="Must be: Critical, High, Medium, Low, or Lowest")
    impact: str = Field(description="Must be: Major, Significant, Moderate, Minor, or No direct impact")
    resolution_status: str = Field(description="Must be: done, cancelled, clarification, or cannot reproduce")
    resolution_text: str = Field(description="A concrete, realistic resolution note in the voice of the agent, matching historical precedents")

def get_llm():
    """Inicializa el modelo de Azure OpenAI con temperatura baja para máxima consistencia determinista."""
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        temperature=0.1
    )

def create_triage_prompt():
    """Define el prompt del sistema inyectando reglas de negocio, contexto RAG y (futuros) candidatos ML."""
    system_template = """You are an expert L2 ITSM support analyst for a pan-European asset management company.
    Your task is to triage a new ticket and deduce the missing or incorrect fields based on historical precedent.
    
    <BUSINESS_RULES>
    CRITICAL SERVICES: Trading Platform, Order Management, Trade Matching, Securities Settlement, Corporate Actions, Fund Pricing, NAV Calculation, Portfolio Accounting, Cash Management, Risk & Compliance Monitoring, Regulatory Reporting, SimCorp Dimension, Rimes Data Feed, Client Reporting.
    NON-CRITICAL SERVICES: Tax Reporting, CRM & Client Portal, Identity & Access Management, SharePoint & File Storage, Outlook & Email, Emailed Support Tickets.
    
    RULES:
    1. If a critical service is fully unavailable, Impact is 'Major' or 'Significant'.
    2. Never output Priority (the system will calculate it deterministically).
    3. The reported service in the new ticket might be wrong (e.g. 'Emailed Support Tickets'). Deduce the REAL service from the description.
    4. Match the resolution_text tone and technical depth of the provided historical context.
    </BUSINESS_RULES>
    
    <HISTORICAL_CONTEXT>
    {historical_context}
    </HISTORICAL_CONTEXT>
    
    <ML_CANDIDATES>
    {ml_candidates}
    </ML_CANDIDATES>
    """
    
    human_template = """
    <NEW_TICKET>
    Summary: {summary}
    Description: {description}
    Reported Service: {reported_service}
    </NEW_TICKET>
    
    Analyze the NEW_TICKET utilizing the HISTORICAL_CONTEXT and ML_CANDIDATES. 
    Output the exact JSON structure required.
    """
    
    return ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", human_template)
    ])

def run_llm_triage(summary: str, description: str, reported_service: str, historical_context: str, ml_candidates: str = "N/A"):
    """Ejecuta la cadena LangChain para obtener el JSON estructurado."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(TriageResult)
    prompt = create_triage_prompt()
    
    chain = prompt | structured_llm
    
    return chain.invoke({
        "summary": summary,
        "description": description,
        "reported_service": reported_service,
        "historical_context": historical_context,
        "ml_candidates": ml_candidates
    })