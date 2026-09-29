# Service Desk AI Copilot 🚀

AI-powered Copilot for IT Service Desk teams. It uses **RAG**, deterministic triage rules, and **Azure OpenAI** to help analysts classify tickets, retrieve relevant historical cases, and draft solutions while keeping the human in control.

Built for the **Swiss{ai}Weeks Hackathon**.

## 🧠 Architecturea

### Backend — Python / FastAPI

- **RAG pipeline** using FAISS/ChromaDB + MiniLM embeddings to retrieve relevant historical tickets.
- **Deterministic priority calculation** based on Urgency × Impact.
- **Azure OpenAI** for solution generation, affected business areas, and AI Auto-complete.
- Main endpoints: `/triage`, `/solution/autocomplete`, `/feedback`.

### Frontend — React / TypeScript / Vite

- Upload raw Jira / Service Desk ticket JSON.
- View AI triage and compare it with benchmark data.
- Review retrieved historical evidence and AI solutions.
- **Human-in-the-Loop:** analysts can validate, modify, or replace AI suggestions and submit feedback.

## ⚙️ Requirements

- Python 3.9+
- Node.js 18+
- npm 9+
- Azure OpenAI resource and deployment

## 🛠️ Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
AZURE_OPENAI_API_KEY="your_api_key"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT_NAME="your_deployment_name"
AZURE_OPENAI_API_VERSION="2024-02-15-preview"
```

Start the API:

```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Start the app:

```bash
npm run dev
```

Frontend: `http://localhost:5173`

## 🚀 Usage

1. Upload a JSON file with Service Desk / Jira tickets.
2. Let the backend perform the initial AI triage.
3. Open a ticket to review RAG evidence and recommended solutions.
4. Validate or edit the suggested resolution, using **AI Auto-complete** when useful.
5. Select the affected business area and submit feedback.

## 📁 Project Structure

```text
backend/
├── api/
│   └── main.py
├── rag/
├── llm/
└── requirements.txt

frontend/
├── src/
│   ├── components/
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── triage.ts
│   └── App.tsx
└── package.json
```

## 🤝 Developer Notes

- RAG changes → `backend/rag/`
- LLM / prompting → `backend/llm/`
- API changes → `backend/api/main.py` + `frontend/src/services/api.ts`
- Triage types → `frontend/src/types/triage.ts`

Never commit `.env`, API keys, `venv/`, or `node_modules/`.
