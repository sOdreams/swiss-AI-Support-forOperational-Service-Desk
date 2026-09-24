# Swiss Life AI Support Agent - Enterprise Backend Architecture & Implementation Guide

Welcome to the ultimate technical and conceptual documentation for the **Swiss Life AI Support Agent** backend. This document serves as an exhaustive, end-to-end blueprint designed to explain, validate, and allow the complete recreation of the system architecture—bridging the gap between non-technical stakeholders and advanced systems architects.

---

## Part 1: Conceptual Overview (For Non-Technical Readers)

Imagine operating a massive, enterprise-grade insurance customer service center (such as Swiss Life) receiving thousands of IT and customer support tickets every single day. Human operators spend hours reading incoming logs, figuring out which specialized department they belong to (e.g., Identity & Access Management vs. Core Application Support), cross-referencing internal historical guidelines, assessing urgency levels (Priority 1 through 4), and drafting accurate resolution steps.

This backend completely automates that cognitive pipeline using **Artificial Intelligence** in under two seconds. Here is how data flows through the system step-by-step:

1. **Ticket Ingestion:** A user or a frontend application submits an incoming ticket containing a short summary and a detailed description of an IT malfunction.
2. **The "Memory" Lookup (RAG - Retrieval-Augmented Generation):** Before querying an expensive LLM, the system performs a localized mathematical search inside a vector database containing historical tickets and company compliance rules. It instantly identifies past cases that structurally resemble the new problem.
3. **The AI Reasoning Engine (LLM):** The system passes the incoming ticket _along with_ the retrieved historical context to a powerful cloud AI model running securely on Microsoft Azure OpenAI.
4. **Structured Decision Making:** The AI reads the data, applies Swiss Life internal logic, and outputs a rigorous, type-safe JSON payload containing:
   - **Category:** Is it an Incident or a Service Request?
   - **Priority:** How urgent is the disruption (P1-P4)?
   - **Assigned Team:** Which department is accountable?
   - **Affected Services:** Which infrastructure components are impacted?
   - **Proposed Solution:** Concrete technical remediation steps for the support technician.
   - **Impact Analysis:** Business and operational risk assessment.

---

## Part 2: Recreating the Backend from a Prompt (Prompt Blueprint)

If you ever need to recreate this exact backend codebase from scratch using an AI generation prompt, use the following master specification:

> **Master Recreation Prompt:** _"Build a production-ready Python FastAPI backend application using LangChain, Pydantic, and ChromaDB. The application must expose a POST endpoint `/api/tickets/analyze` that accepts a ticket summary and description. It must perform a local vector similarity search using HuggingFace embeddings (`all-MiniLM-L6-v2`) against a local ChromaDB persistence directory (`./chroma_data`) to retrieve historical context. It must then pass the query and context to Microsoft Azure OpenAI (`AzureChatOpenAI`) using a structured Pydantic output parser (`JsonOutputParser`) to enforce a strict JSON schema (`AIRecommendation`) containing category, priority, assigned team, affected services, proposed solution, and impact analysis. Configure settings securely using `pydantic-settings` and a `.env` file."_

---

## Part 3: Technical Architecture & Technology Stack

- **Web Framework:** `FastAPI` — High-performance, asynchronous Python web framework providing automatic Swagger UI documentation (`/docs`).
- **AI Orchestration Framework:** `LangChain` — Standard framework for chaining prompts, retrievers, and structured output parsers.
- **Vector Store & Embeddings:** `ChromaDB` (Local vector store) paired with HuggingFace Embeddings (`all-MiniLM-L6-v2` running locally on CPU/GPU for semantic similarity search).
- **Language Model (LLM):** Microsoft Azure OpenAI (`gpt-4o` or `gpt-4o-mini`) accessed via secure enterprise cloud endpoints.
- **Data Validation & Config:** `Pydantic` & `pydantic-settings` — Ensures strict runtime type checking and secure environment variable parsing.

---

## Part 4: Project Structure and File Breakdown

```
backend/
├── main.py                # FastAPI application entrypoint and router configuration
├── src/
│   ├── agent.py           # Core RAG chain logic and Azure OpenAI prompt orchestration
│   ├── config.py          # Environment variable parser and global settings
│   └── retriever.py       # ChromaDB connection and vector similarity search logic
├── chroma_data/           # Local persistent directory for vector embeddings
├── .env                   # Private configuration keys (API keys, endpoints)
└── requirements.txt       # Python package dependencies
```

---

## Part 5: Deep-Dive Function & Code Analysis

### 1. Configuration Layer (`src/config.py`)

This file defines a robust settings class inheriting from `pydantic_settings.BaseSettings`. It automatically loads environment variables from the `.env` file and validates their types at startup.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    CHAT_MODEL_DEPLOYMENT_NAME: str = "gpt-4o"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

- **Role:** Centralized configuration management. It protects against missing configuration errors and keeps enterprise secrets strictly out of source code.

### 2. Retrieval Layer (`src/retriever.py`)

Responsible for semantic search. When a ticket arrives, this component embeds the text locally using HuggingFace and queries the local ChromaDB vector store to find past historical resolutions.

- **Theoretical Concept:** _Vector Embeddings & Semantic Search_. Words are converted into high-dimensional numerical vectors. Meaning-based proximity allows the system to find relevant documents even if exact keywords do not match.

### 3. Agent & AI Orchestration Layer (`src/agent.py`)

This component orchestrates the Retrieval-Augmented Generation (RAG) pipeline, connecting historical context with Azure OpenAI and enforcing strict JSON compliance.

```python
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
```

### 4. API Entrypoint Layer (`main.py`)

Exposes the asynchronous endpoints via FastAPI, serving as the interface between the client application and the RAG agent.

```python
from fastapi import FastAPI
from pydantic import BaseModel
from src.agent import analyze_ticket_with_ai

app = FastAPI(title="Swiss Life AI Support Agent", version="1.0.0")

class TicketRequest(BaseModel):
    summary: str
    description: str

@app.post("/api/tickets/analyze")
def analyze_ticket(ticket: TicketRequest):
    result = analyze_ticket_with_ai(ticket.summary, ticket.description)
    return result
```

---

## Part 6: Execution & Deployment Guide

1. Clone the repository and navigate to the `backend/` directory.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   ```
3. Install the required dependencies:
   ```bash
   pip install fastapi uvicorn langchain langchain-openai langchain-chroma pydantic-settings python-dotenv
   ```
4. Configure your `.env` file in the root directory with valid Azure credentials.
5. Launch the development server with live-reload enabled:
   ```bash
   uvicorn main:app --reload
   ```
6. Open your browser and navigate to `http://127.0.0.1:8000/docs` to interact with the Swagger UI.
