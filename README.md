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
2. **Pull the Mistral model**: `ollama pull mistral`
3. **Backend**: See `backend/README.md` for Python setup which will run on localhost:5000
4. **Frontend**: See `frontend/README.md` for setting up front end and open localhost:3000 in browser
5. **MCP**: Open `mcp/README.md` for setting up MCP server which will run on localhost:9000

## Development
- All code is in `backend/`, `frontend/`, and `mcp/` folders
- System prompt is in `backend/system_prompt.txt`

## License
MIT
