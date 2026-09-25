# Phase 1: Data Analysis & Splitting - Triage Hackathon

## Objetivo

Preparar y sanitizar 20.000 tickets sintéticos de Jira para alimentar un sistema de triaje RAG[cite: 4]. El conjunto original simula datos reales y contiene ruido intencionado, servicios mal asignados y resoluciones inconsistentes[cite: 4].

## Descubrimientos Clave

- **Ruido Sintético Masivo:** La gran mayoría de los comentarios recurrentes carecen de valor técnico. El cierre genérico "problem fixed." aparece 5.851 veces[cite: 3]. Las plantillas administrativas de enrutamiento, como "initial triage assigned to service desk and reviewed against the service catalogue.", aparecen miles de veces (3.850 solo para Service Desk)[cite: 3].
- **Aleatoriedad Plana en Asignaciones:** Los 11 equipos documentados tienen exactamente 30 agentes cada uno[cite: 5]. El equipo principal, "Service Desk", gestiona 5.423 tickets con una distribución prácticamente uniforme de unos 180,8 tickets por agente[cite: 5]. Esto invalida el uso de ML predictivo para el campo `Assignee` y refuerza la necesidad de buscar coincidencias semánticas mediante RAG.
- **Métricas de Prioridad Aleatorias:** Los campos de `Priority`, `Urgency` e `Impact` en el historial no guardan correlación real con el problema[cite: 4]. Fueron generados de manera independiente y deben ser ignorados como evidencia de entrenamiento[cite: 4].

## Artefactos Generados

Se implementó un filtrado de tres niveles (exacto para frases cortas, prefijos para plantillas largas) y se extrajeron los campos aleatorios de los tickets destinados al VectorDB. Los archivos generados en `backend/data/processed/` son:

- `routing_dataset.json` (20.000 tickets): Datos completos para la jerarquía de enrutamiento.
- `rag_dataset_soft.json` (15.885 tickets): Filtro básico sin coincidencias exactas como "done".
- `rag_dataset_balanced.json`: Filtro óptimo sin plantillas de enrutamiento robótico.
- `rag_dataset_strict.json` (5.814 tickets): Filtro agresivo que deja únicamente resoluciones técnicas densas.
