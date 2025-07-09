# local-llm-chatbot

A simple AI chatbot application that runs locally using Ollama (Mistral Small 3.1) as the LLM backend. The app features a browser-based frontend and a customizable system prompt for the AI assistant's persona.

## Features
- Local backend using FastAPI (Python)
- Frontend chat UI (HTML/JS/CSS)
- Uses Ollama with Mistral Small 3.1 model
- Customizable system prompt for AI personality
- Mac compatible

## Setup
1. **Install Ollama**: https://ollama.com/download
2. **Pull the Mistral model**: `ollama pull mistral:3.1`
3. **Backend**: See `backend/README.md` for Python setup
4. **Frontend**: Open `frontend/index.html` in your browser

## Development
- All code is in `backend/` and `frontend/` folders
- System prompt is in `backend/system_prompt.txt`

## License
MIT