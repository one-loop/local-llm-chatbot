# Backend - Local LLM Chatbot

## Requirements
- Python 3.8+
- [Ollama](https://ollama.com/) running locally (with the Mistral Small 3.1 model pulled)

## Setup

1. **Create a virtual environment (recommended):**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make sure Ollama is running and the Mistral model is available:**
   ```bash
   ollama pull mistral:3.1
   ollama run mistral:3.1
   ```

4. **Start the FastAPI server (on port 5000):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 5000
   ```
   The backend will be available at: http://localhost:5000

## System Prompt
- Edit `system_prompt.txt` to customize the AI assistant's persona and behavior.
- Restart the backend server to apply changes.

## Troubleshooting
- **Error loading ASGI app:** Make sure you are in the `backend` directory when running `uvicorn main:app ...`.
- **Ollama errors:** Ensure Ollama is running and the model is pulled.
- **CORS errors:** See below.

## (Optional) CORS for Local Development
If you get CORS errors in the browser, you can add CORS support to FastAPI:
1. Install CORS middleware:
   ```bash
   pip install fastapi[all]
   ```
2. Add this to `main.py`:
   ```python
   from fastapi.middleware.cors import CORSMiddleware

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ``` 