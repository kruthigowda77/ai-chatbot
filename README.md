# AI Chatbot

A full-stack AI chatbot built from scratch with a **Python FastAPI** backend, a **vanilla JavaScript** frontend, and an LLM API (Google Gemini by default, or OpenAI). Supports multi-turn conversations, input validation, layered error handling, and automated tests.
   ![Chatbot screenshot](docs/screenshot.png)

## Features

- **Clean chat interface**: responsive design that works on desktop and mobile
- **Conversation memory**: multi-turn context, so the bot remembers earlier messages
- **Provider-agnostic**: switch between Gemini and OpenAI by changing environment variables, with no code changes
- **Secure by design**: API key stays on the server; client-supplied history can't inject system prompts
- **Robust error handling**: friendly messages for timeouts, rate limits, and service outages; detailed server logs for developers
- **Automated tests**: 10 pytest tests with a mocked LLM, so they run in under a second and cost nothing

## Tech Stack

| Layer    | Technology                                   |
|----------|----------------------------------------------|
| Frontend | HTML, CSS, JavaScript (Fetch API)            |
| Backend  | Python, FastAPI, Uvicorn, Pydantic           |
| AI       | Google Gemini via OpenAI-compatible API      |
| Testing  | pytest, FastAPI TestClient                   |
| Tools    | Git, GitHub, VS Code                         |

## Architecture

```
┌──────────────┐  POST /api/chat   ┌──────────────────┐   HTTPS   ┌──────────────┐
│   Browser    │ ────────────────► │  FastAPI backend │ ────────► │   LLM API    │
│  (HTML/JS)   │ ◄──────────────── │  (Python)        │ ◄──────── │  (Gemini)    │
└──────────────┘   {"reply": ...}  └──────────────────┘           └──────────────┘
```

The backend serves the frontend and exposes a REST API. The API key never leaves the server.

### How conversation memory works

LLM APIs are stateless. The model remembers nothing between requests. To maintain context, the frontend keeps the conversation history and sends it with every request. The backend:

1. Validates it, accepting only `user` and `assistant` roles, so clients can't inject `system` instructions
2. Trims it to the last 20 messages to control cost and stay within the model's context window
3. Adds the system prompt and the new message, then calls the LLM

## Project Structure

```
ai-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, endpoints, error handlers
│   │   ├── config.py        # Loads settings from .env
│   │   ├── schemas.py       # Request/response validation (Pydantic)
│   │   └── services/
│   │       └── llm.py       # LLM client and error translation
│   ├── tests/
│   │   └── test_api.py      # Automated API tests (mocked LLM)
│   ├── check_ai.py          # Quick script to verify the AI connection
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example         # Template for required settings
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) (or an OpenAI API key)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR-USERNAME/ai-chatbot.git
cd ai-chatbot/backend

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file from the template
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
```

Then open `backend/.env` and add your API key.

### Run

```bash
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

### Run the tests

```bash
python -m pytest -v
```

## Configuration

All settings live in `backend/.env`:

| Variable       | Description                                      | Example                                                    |
|----------------|--------------------------------------------------|------------------------------------------------------------|
| `LLM_API_KEY`  | Your API key                                     | `AIza...` (Gemini) or `sk-proj-...` (OpenAI)                |
| `LLM_MODEL`    | Model name                                       | `gemini-3.5-flash-lite`                                    |
| `LLM_BASE_URL` | API address (leave empty for OpenAI)             | `https://generativelanguage.googleapis.com/v1beta/openai/` |

## API Reference

Interactive docs are available at **http://127.0.0.1:8000/docs** while the server is running.

**`POST /api/chat`**

Request:
```json
{
  "message": "What is my name?",
  "history": [
    { "role": "user", "content": "My name is Kruthi" },
    { "role": "assistant", "content": "Nice to meet you, Kruthi!" }
  ]
}
```

Response:
```json
{ "reply": "Your name is Kruthi!" }
```

Errors return an appropriate status code (`422`, `429`, `503`, etc.) with `{ "detail": "friendly message" }`.

**`GET /api/health`** returns `{ "status": "ok", "model": "..." }`

## Roadmap

- [x] Phase 1: Working chatbot with memory, error handling, and tests
- [ ] Phase 2: Streaming responses, typing indicator, Markdown rendering
- [ ] Phase 3: Database, saved chat history, user authentication
- [ ] Phase 4: Chatbot personalities, PDF upload, RAG with a vector database, web search
- [ ] Phase 5: Voice input and text-to-speech
- [ ] Phase 6: Admin dashboard, security hardening, deployment

## Author

**Kruthi A**