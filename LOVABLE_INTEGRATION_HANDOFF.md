# Lovable Integration Handoff – IDP Medical Agent API

**For:** Person building the Lovable frontend  
**From:** Backend / API owner  
**Purpose:** Everything you need to connect a Lovable (or any) frontend to the IDP Medical Agent backend.

---

## 1. What You’re Integrating With

- **Backend:** IDP Medical Agent – answers questions about Ghana health facilities (counts, services, risk, gaps, “what does X offer?”, chat, etc.).
- **API:** REST API (FastAPI) that wraps the same logic the CLI uses. You call HTTP endpoints; the backend returns JSON.

You will **not** run Lovable’s backend. You will:
1. Get the backend code/zip and run the **API server** (or use a deployed URL we give you).
2. Build the **frontend in Lovable** and point it at that API base URL.

---

## 2. Running the Backend API (Your Side or Theirs)

Whoever has the repo:

```bash
cd idp-medical-agent
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

- **Local:** API is at `http://localhost:8000`
- **Same machine, frontend on another port:** Use `http://localhost:8000` as API base URL in the frontend
- **Deployed server:** Use `https://your-api-domain.com` (or `http://IP:8000`) as API base URL

**Environment:** Backend needs a `.env` (or env vars) with `OPENAI_API_KEY` for RAG and Medical Reasoning. Ask the backend owner for a sample `.env.example` if you need to run it yourself.

---

## 3. API Base URL (What to Put in Lovable)

- **Local dev:** `http://localhost:8000`
- **Production:** Whatever URL the backend is deployed at (e.g. `https://api.yourproject.com`)

No trailing slash. All endpoints below are relative to this base (e.g. `POST {baseUrl}/api/query`).

---

## 4. Endpoints You Need

### Health check (optional)

- **GET** `/api/health`
- **Response:** `{ "status": "ok", "service": "idp-medical-agent" }`
- Use to check the backend is up before showing the main UI.

---

### Single question (search / one-shot Q&A)

- **POST** `/api/query`
- **Request body:**
  ```json
  { "query": "Which regions lack dialysis?" }
  ```
- **Response:**
  ```json
  {
    "answer": "Full text answer (markdown-friendly)...",
    "intent": "local_facility_query",
    "sub_agent": "local_csv",
    "used_medical_reasoning": false
  }
  ```
- **Use in Lovable:** Search box or “Ask” button → send `query` → show `answer`. Optionally show `sub_agent` or “Medical reasoning used” when `used_medical_reasoning` is true.

---

### Chat (multi-turn)

- **POST** `/api/chat`
- **Request body:**
  ```json
  { "message": "What services does Methodist Clinic offer?" }
  ```
- **Response:**
  ```json
  {
    "reply": "Full text reply...",
    "intent": "local_facility_query",
    "sub_agent": "local_csv"
  }
  ```
- **Use in Lovable:** For each user message, send one `POST` with `message`; append the `reply` to the chat UI. The backend does **not** keep conversation history; the frontend can keep messages in state for display.

---

### Guided menu (optional – for “I need care near me”, “Find gaps”, etc.)

- **GET** `/api/guided-options`
- **Response:**
  ```json
  {
    "options": [
      {
        "id": "care_near_me",
        "label": "I need care near me",
        "short": "e.g. I'm pregnant / need maternity; I live in [city]",
        "example": "I'm pregnant, where should I go? I live in Accra"
      },
      {
        "id": "gaps",
        "label": "Find gaps",
        "short": "Where is a type of care missing?",
        "example": "Which regions lack dialysis?"
      },
      {
        "id": "find",
        "label": "Find facilities",
        "short": "Where can I get a specific care?",
        "example": "Facilities with maternity care"
      },
      {
        "id": "regional",
        "label": "Regional view",
        "short": "What capabilities exist by region?",
        "example": "What does Accra have?"
      },
      {
        "id": "verify",
        "label": "Verify a claim",
        "short": "Can a facility really do X?",
        "example": "Can Korle Bu do dialysis?"
      },
      {
        "id": "custom",
        "label": "Custom question",
        "short": "Type your own question",
        "example": ""
      }
    ]
  }
  ```
- **Use in Lovable:** Render buttons or cards from `options`. When the user picks one:
  - For **custom:** open a text input and send that text to `POST /api/query` with `{"query": userInput}`.
  - For **care_near_me:** you can prompt for “Type of care” and “City” then build a query like `I'm pregnant, where should I go? I live in Accra` and send to `POST /api/query`.
  - For **gaps:** prompt for “Capability (e.g. dialysis)” then send `Which regions lack dialysis?` to `POST /api/query`.
  - For **find:** prompt for “Care type” then send `Facilities with maternity care` to `POST /api/query`.
  - For **regional:** prompt for “Region (e.g. Accra)” then send `What capabilities exist in Accra?` to `POST /api/query`.
  - For **verify:** prompt for facility name and capability, then send e.g. `Can Korle Bu do dialysis?` to `POST /api/query`.

You can also ignore the guided options and only use `POST /api/query` with a single search input.

---

### Guided query (same as single question)

- **POST** `/api/guided-query`
- Same request/response as **POST** `/api/query`. Use when the user chose a guided option and you built the full question (e.g. `Which regions lack dialysis?`).

---

## 5. Request Headers

Send JSON and accept JSON:

```
Content-Type: application/json
Accept: application/json
```

(Standard for fetch/axios when using `body: JSON.stringify(...)`.)

---

## 6. CORS

The API is configured to allow requests from **any origin** (`*`). So a Lovable app on `http://localhost:5173` or a deployed frontend on another domain can call the API without CORS errors. If the backend is later restricted to specific origins, you’ll need to add your frontend URL to their allowlist.

---

## 7. Example Frontend Usage (Copy-Paste Reference)

**Single question (e.g. fetch):**

```js
const response = await fetch(`${API_BASE_URL}/api/query`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "How many hospitals are in Accra?" }),
});
const data = await response.json();
// data.answer, data.intent, data.sub_agent, data.used_medical_reasoning
```

**Chat:**

```js
const response = await fetch(`${API_BASE_URL}/api/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userMessage }),
});
const data = await response.json();
// data.reply, data.intent, data.sub_agent
```

**Guided options (for menu):**

```js
const response = await fetch(`${API_BASE_URL}/api/guided-options`);
const data = await response.json();
// data.options = array of { id, label, short, example }
```

Replace `API_BASE_URL` with `http://localhost:8000` (dev) or the deployed API URL.

---

## 8. Quick Reference Table

| What you want           | Method | Endpoint             | Body / Params |
|-------------------------|--------|----------------------|----------------|
| Check backend is up     | GET    | `/api/health`        | none           |
| One-shot question       | POST   | `/api/query`         | `{ "query": "..." }` |
| One chat message        | POST   | `/api/chat`          | `{ "message": "..." }` |
| Get guided menu options| GET    | `/api/guided-options`| none           |
| Run guided-built query  | POST   | `/api/guided-query`  | `{ "query": "..." }` |

---

## 9. Interactive API Docs

If you have the backend running, open:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

You can try every endpoint from the browser and see exact request/response shapes.

---

## 10. What to Ask the Backend Owner

- **API base URL** for dev and for production (if they deploy it).
- **.env.example** (or list of env vars) if you need to run the backend yourself.
- Whether they will **deploy** the API or expect you to run it locally while developing the Lovable app.

---

**You’re ready to build the Lovable UI and point it at this API using the endpoints and examples above.**
