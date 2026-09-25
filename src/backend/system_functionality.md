# README: Arquitectura del Sistema de Triaje (Fases 2 a 5)

## Descripción General

Este documento detalla la implementación del backend funcional para el _Swiss AI Weeks Hackathon_. El sistema procesa tickets de soporte en bruto, identifica el servicio real afectado ignorando clasificaciones erróneas, asigna la resolución a los equipos adecuados y calcula la prioridad de manera matemáticamente estricta utilizando una arquitectura modular de Generación Aumentada por Recuperación (RAG) combinada con reglas deterministas.

## Componentes del Pipeline

### 1. Motor de Búsqueda Semántica (VectorDB)

- **Tecnología:** ChromaDB y LangChain.
- **Modelo de Embeddings:** `all-MiniLM-L6-v2` (ejecución local).
- **Estrategia de Datos:** Se implementó el corpus `rag_dataset_strict.json` para poblar la base vectorial. Esto asegura que el sistema recupere únicamente tickets históricos que contienen resoluciones técnicas reales, eliminando por completo las plantillas administrativas estandarizadas que contaminan el texto de salida.

### 2. Motor de Reglas Deterministas

- **Tecnología:** Código Python puro (`rules/priority.py`).
- **Lógica:** Implementa la matriz oficial de Prioridad (Urgencia vs Impacto).
- **Función:** Intercepta la deducción de impacto y urgencia del LLM y calcula la prioridad final de manera inmutable. Esto garantiza la máxima puntuación en la evaluación al evitar que el LLM alucine niveles de prioridad inconsistentes.

### 3. Orquestador LLM y Estructuración de Datos

- **Tecnología:** Azure OpenAI, Pydantic, LangChain (`llm/triage.py`).
- **Validación:** Utiliza esquemas Pydantic (`TriageResult`) para forzar que la respuesta del modelo sea un JSON con llaves exactas y valores restringidos (ej. resoluciones limitadas a `done`, `cancelled`, `clarification`, `cannot reproduce`).
- **Prompt Engineering:** Se inyectaron directrices de negocio estrictas, incluyendo la lista de servicios críticos, la orden de ignorar métricas de prioridad heredadas, y barreras contra la generación de texto robótico.

### 4. API Gateway

- **Tecnología:** FastAPI y Uvicorn (`api/main.py`).
- **Flujo de Ejecución:**
  1.  Recibe el ticket en formato JSON a través del endpoint `POST /triage`.
  2.  Consulta ChromaDB para recuperar los 3 tickets históricos más similares.
  3.  Envía el ticket original y el contexto recuperado a Azure OpenAI.
  4.  Sobrescribe la prioridad generada por el modelo con el cálculo determinista.
  5.  Devuelve el veredicto final estructurado y listo para la evaluación.
