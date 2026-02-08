# Using This Backend With a Different Frontend (e.g. Lovable AI)

Yes. This tool is the **backend**. You can put it behind an **API** and use **any frontend**—including one built in **Lovable AI**, React, Vue, or a simple HTML page.

---

## How It Works

1. **Backend** = this repo (CLI + new API server).
2. **API server** = run `api.py` with uvicorn; it exposes REST endpoints.
3. **Frontend** = your Lovable (or other) app; it calls those endpoints over HTTP.

Lovable builds the **frontend**; it does **not** host this Python backend. You run the backend yourself (or deploy it to a server) and point the Lovable app at its URL.

---

## 1. Start the API Backend

From the project root (where `api.py` and `main.py` live):

```bash
cd /path/to/idp-medical-agent
pip install -r requirements.txt   # includes fastapi, uvicorn
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Or:

```bash
python api.py
```

The API will be at **http://localhost:8000** (or http://YOUR_SERVER:8000 if deployed).

---

## 2. API Endpoints Your Frontend Can Call

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | Health check. Returns `{"status": "ok"}`. |
| POST | `/api/query` | **Single question.** Body: `{"query": "Which regions lack dialysis?"}`. Returns `{ "answer": "...", "intent": "...", "sub_agent": "...", "used_medical_reasoning": true/false }`. |
| POST | `/api/chat` | **One chat message.** Body: `{"message": "What services does Methodist Clinic offer?"}`. Returns `{ "reply": "...", "intent": "...", "sub_agent": "..." }`. Use this for a chat UI; send each user message and display the `reply`. |
| GET | `/api/guided-options` | **Menu for guided planning.** Returns `{ "options": [ {"id": "care_near_me", "label": "I need care near me", ...}, ... ] }`. Use this to build buttons or a dropdown instead of the CLI menu. |
| POST | `/api/guided-query` | Same as `/api/query`; use when the user picked a guided option and you built the full question (e.g. "Which regions lack dialysis?"). |

**Docs:** Open **http://localhost:8000/docs** in a browser for Swagger UI (try the endpoints from the browser).

---

## 3. Using With Lovable AI

1. **Build your frontend in Lovable**  
   - Describe the UI you want (e.g. “Chat interface for Ghana facility questions”, “Search box + results”, “Guided menu + answer area”).  
   - Lovable will generate a React (or other) app.

2. **Point the frontend at this backend**  
   - In the Lovable app, set the **API base URL** to your backend, e.g. `http://localhost:8000` (dev) or `https://your-api.example.com` (production).  
   - Call:
     - **Single question:** `POST /api/query` with `{ "query": userInput }`, show `response.answer`.
     - **Chat:** `POST /api/chat` with `{ "message": userInput }`, show `response.reply`.
     - **Guided menu:** `GET /api/guided-options`, render buttons/options; when user picks one (and you optionally ask for “dialysis” or “Accra”), build the question and call `POST /api/query` or `POST /api/guided-query` with that question.

3. **Run both**  
   - Backend: `uvicorn api:app --host 0.0.0.0 --port 8000` (on your machine or a server).  
   - Frontend: run the Lovable app (e.g. `npm run dev`) and use the same network (or deploy frontend and backend and set CORS/origins as needed).

**CORS:** The API allows all origins by default (`allow_origins=["*"]`) so a frontend on another port or domain can call it. In production, restrict `allow_origins` to your frontend URL.

---

## 4. Example: Frontend Calling the API

**Single question (e.g. search box):**

```javascript
const res = await fetch("http://localhost:8000/api/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "How many hospitals are in Accra?" }),
});
const data = await res.json();
console.log(data.answer);           // the text answer
console.log(data.sub_agent);        // e.g. "local_csv"
console.log(data.used_medical_reasoning);
```

**Chat (e.g. chat bubble UI):**

```javascript
const res = await fetch("http://localhost:8000/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "What services does Methodist Clinic offer?" }),
});
const data = await res.json();
console.log(data.reply);
```

**Guided menu:**

```javascript
const res = await fetch("http://localhost:8000/api/guided-options");
const data = await res.json();
// data.options = [{ id: "care_near_me", label: "I need care near me", ... }, ...]
// Build UI from data.options; when user picks one (+ optional extra), send full question to /api/query
```

---

## 5. Summary

| Question | Answer |
|----------|--------|
| Can this backend be used with a different frontend? | **Yes.** |
| Can it be used with Lovable AI? | **Yes.** Lovable builds the frontend; this repo runs the backend API. |
| What do I need to do? | Run `uvicorn api:app --host 0.0.0.0 --port 8000`, then in Lovable (or any frontend) call `POST /api/query` or `POST /api/chat` and `GET /api/guided-options` as above. |

The backend stays as-is; the **API layer** (`api.py`) is the bridge between this tool and any frontend or UI.
