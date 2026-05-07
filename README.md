# SO/Expert·System

A full-stack, local-first analytics platform built on the **Stack Overflow Developer Survey 2024** (90,184 respondents). It combines a React dashboard, an Express/TypeORM REST API backed by PostgreSQL, and a Python ML pipeline that predicts developer salaries and explains them with SHAP.

---

## ✨ Features

| Area | What's inside |
|---|---|
| **Dashboard** | Interactive charts — top languages used/wanted, DevOps tool adoption, median salary by developer role |
| **Career Advisor** | Salary predictor powered by a `RandomForestRegressor`; SHAP feature-importance explanations |
| **REST API** | `/api/stats`, `/api/predict` endpoints with TypeORM + PostgreSQL |
| **ML Pipeline** | Automated ETL (`train.py`), joblib model persistence, Python ↔ Node bridge (`predict.py`) |
| **DevOps** | One-command Docker stack (PostgreSQL 15 + pgAdmin 4) |

---

## 🗂️ Project Structure

```
expert-system/
├── client/               # React + Vite + TypeScript frontend
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx      # Survey analytics charts
│       │   └── CareerAdvisor.tsx  # Salary prediction UI
│       ├── api/client.ts          # Typed API client
│       └── types/                 # Shared TypeScript types (client-side)
│
├── server/               # Express + TypeORM backend
│   └── src/
│       ├── routes/
│       │   ├── stats.ts           # GET /api/stats
│       │
│       │   └── predict.ts         # POST /api/predict
│       ├── services/
│       │   └── mlBridge.ts        # Spawns Python predict.py
│       ├── entities/              # TypeORM entity definitions
│       └── config/database.ts     # DataSource configuration
│
├── ml/                   # Python ML pipeline
│   ├── scripts/
│   │   ├── train.py       # ETL + RandomForestRegressor training
│   │   └── predict.py     # Inference script (stdin → stdout JSON)
│   └── requirements.txt
│
├── shared/               # Types shared between client & server
├── docker-compose.yml    # PostgreSQL 15 + pgAdmin 4
├── package.json          # Root workspace scripts
└── .env                  # Environment variables (see below)
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version |
|---|---|
| Node.js | ≥ 18 |
| Python | ≥ 3.10 |
| Docker & Docker Compose | any recent version |

### 1 — Clone & install dependencies

```bash
git clone https://github.com/mohammedeissa7/expert-system.git
cd expert-system
npm run install:all
```

### 2 — Configure environment variables

Copy the example and fill in your values:

```bash
cp .env .env.local   # then edit .env.local
```

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3001` | Express server port |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `survey_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |

### 3 — Start the database

```bash
docker compose up -d
```

- **PostgreSQL** → `localhost:5432`
- **pgAdmin 4** → `http://localhost:5050` (login: `admin@admin.com` / `admin`)

### 4 — Set up the Python ML pipeline

```bash
cd ml
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python scripts/train.py   # ETL + model training (creates model artifact)
```

### 5 — Run the full stack

From the project root:

```bash
npm run dev
```

This concurrently starts:
- **Server** → `http://localhost:3001`
- **Client** → `http://localhost:5173`

---

## 🔌 API Reference

### `GET /api/health`
Returns server status and timestamp.

### `GET /api/stats`
Returns aggregated survey statistics:
- Total respondents, average global salary, AI tool adoption, online learners %
- Top languages used & wanted
- DevOps tool adoption
- Median salary by developer role


### `POST /api/predict`
Predicts a developer's salary with SHAP explanations.

**Request body:**
```json
{
  "yearsExperience": 5,
  "education": "Bachelor's degree",
  "devType": "Full-stack developer",
  "country": "United States",
  "languages": ["JavaScript", "TypeScript", "Python"]
}
```

**Response:**
```json
{
  "data": {
    "predictedSalary": 125000,
    "shapValues": { "yearsExperience": 15000, "devType": 8000, ... }
  }
}
```

---

## 🛠️ Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start server + client concurrently |
| `npm run dev:server` | Start Express server only |
| `npm run dev:client` | Start Vite dev server only |
| `npm run install:all` | Install all workspace dependencies |
| `npm run build` | Build the client production bundle |
| `python ml/scripts/train.py` | Run ETL and train the ML model |

---

## 🧰 Tech Stack

### Frontend
- **React 18** + **Vite** + **TypeScript**
- **React Router v6** — client-side routing
- **Chart.js** + **react-chartjs-2** — interactive data visualizations

### Backend
- **Express.js** + **TypeScript**
- **TypeORM** — database ORM
- **PostgreSQL 15** — persistent data store

### ML / Data
- **scikit-learn** — `RandomForestRegressor` salary model
- **SHAP** — feature importance / explainability
- **pandas** + **numpy** — data wrangling
- **joblib** — model serialization

### DevOps
- **Docker Compose** — PostgreSQL + pgAdmin
- **concurrently** — multi-process dev runner

---

## 📊 Data Source

**Stack Overflow Developer Survey 2024**
- 90,184 respondents worldwide
- 84 questions covering tools, salaries, experience, education, and more
- Raw CSV available at [survey.stackoverflow.co](https://survey.stackoverflow.co/)

---

## 📄 License

MIT © Eissa
