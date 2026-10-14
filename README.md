# FinSight AI — Full-stack demo
React + TypeScript frontend, FastAPI backend, SQLite database, JWT login, dashboard, transaction APIs, anomaly alerts, and a data-grounded assistant. Uses synthetic demo data only.

## Run on Windows
### Backend (Terminal 1)
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

### Frontend (Terminal 2)
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

Demo login: `demo@finsight.local` / `DemoPass123!`
Change SECRET_KEY before any deployment. This is an educational demo, not investment advice. Do not use real financial data.
