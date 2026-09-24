> **FAISS retrieval is implemented on this branch.** Start with [backend/README.md](backend/README.md) for install/build/API/Python usage. It returns **Top-50 distinct evidence groups with rank**, independently of routing. AI coding agents should read [AGENTS.md](AGENTS.md) and the [integration handoff](docs/RETRIEVAL_HANDOFF.md). The older frontend prototype description below predates this backend.

# Service Desk Copilot

Aplicación frontend para revisar tickets de soporte con asistencia de IA. La interfaz permite comparar el ticket original con una propuesta generada por IA, evaluar la recomendación y registrar la decisión del analista humano.

## Descripción del proyecto

Este proyecto simula un panel de trabajo para un equipo de soporte/IT Service Desk. La idea principal es separar tres capas:

1. El ticket original (fuente de verdad)
2. La propuesta sugerida por IA
3. La decisión final del analista (aprobar, editar o rechazar)

La app muestra:

- una cola de tickets con búsqueda y filtro,
- el detalle del ticket y sus comentarios,
- la comparación entre datos reales y propuesta de IA,
- el borrador de respuesta,
- las fuentes utilizadas por la IA,
- y la revisión humana final.

## Stack tecnológico

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Lucide React

## Requisitos previos

Asegúrate de tener instalado:

- Node.js 18 o superior
- npm 9 o superior

Puedes verificarlo con:

```bash
node -v
npm -v
```

## Estructura del proyecto

```text
SwissAITest-AI-Support-Agent/
├── README.md
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── eslint.config.js
│   └── src/
│       ├── App.tsx
│       ├── components/
│       ├── data/
│       ├── features/
│       ├── lib/
│       ├── services/
│       ├── types/
│       ├── index.css
│       └── main.tsx
└── .gitignore
```

## Instalación

Desde la raíz del proyecto:

```bash
cd frontend
npm install
```

## Ejecución local

Inicia el servidor de desarrollo:

```bash
cd frontend
npm run dev
```

Luego abre la URL que indique Vite, normalmente algo como:

```text
http://localhost:5173
```

## Build de producción

Para compilar la aplicación para producción:

```bash
cd frontend
npm run build
```

El resultado se generará en la carpeta:

```text
frontend/dist/
```

## Variables de entorno

La aplicación intenta usar una API si está configurada. Por defecto, el cliente usa:

```text
http://localhost:8000
```

Puedes definir una variable de entorno en un archivo `.env` dentro de `frontend`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Si no existe backend, la app sigue funcionando con datos mock dentro del frontend.

## Datos actuales del proyecto

La aplicación usa datos de ejemplo en:

- [frontend/src/data/mockTickets.ts](frontend/src/data/mockTickets.ts)
- [frontend/src/data/mockAiProposals.ts](frontend/src/data/mockAiProposals.ts)

Esto permite ejecutar la interfaz sin depender de una base de datos o servicio real.

## Flujo funcional principal

1. El usuario selecciona un ticket desde la cola.
2. Se muestra el detalle original del ticket.
3. La IA propone valores para campos como prioridad, equipo de servicio, tipo de solicitud, etc.
4. El analista puede:
   - aprobar,
   - corregir manualmente,
   - o rechazar la propuesta.
5. La decisión se guarda en el estado local de la interfaz.

## Puntos importantes para replicar o adaptar

- La lógica principal vive en [frontend/src/App.tsx](frontend/src/App.tsx)
- Los componentes de IU se agrupan por dominio en [frontend/src/features](frontend/src/features)
- Los tipos están en [frontend/src/types](frontend/src/types)
- La integración con API está pensada en [frontend/src/services/api.ts](frontend/src/services/api.ts)

## Nota sobre backend

Este repositorio actualmente contiene una interfaz frontend funcional con mocks, pero no incluye un backend real ni una base de datos. Si se quiere conectar con un servicio real, se debe implementar una API que exponga endpoints tipo:

- `GET /tickets`
- `GET /tickets/:issueId`
- `POST /tickets/:issueId/assist`
- `POST /feedback`

La interfaz ya está preparada para consumir esos endpoints a través del servicio `api.ts`.

## Comandos útiles

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

## Resumen

Este proyecto es un prototipo de panel para revisión asistida por IA en soporte técnico, pensado para validar propuestas de clasificación y respuesta antes de aplicarlas. Está listo para ejecutarse localmente con datos mock y puede evolucionar hacia una integración real con un backend y una API de IA.

## Recomendación para IA o colaboradores

Si vas a reutilizar este proyecto con una IA o con un agente, usa este flujo:

```bash
cd frontend
npm install
npm run dev
```

Y luego revisa:

- [frontend/src/App.tsx](frontend/src/App.tsx)
- [frontend/src/features/tickets/TicketDetail.tsx](frontend/src/features/tickets/TicketDetail.tsx)
- [frontend/src/features/ai/AiProposalPanel.tsx](frontend/src/features/ai/AiProposalPanel.tsx)
- [frontend/src/services/api.ts](frontend/src/services/api.ts)

Eso te permitirá entender rápidamente cómo funciona el flujo de tickets, la IA y la revisión humana.

