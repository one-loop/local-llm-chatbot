# local-llm-chatbot

A simple AI chatbot application that runs locally using Ollama (Mistral Small 3.1) as the LLM backend. The app features a browser-based frontend and a customizable system prompt for the AI assistant's persona.

## Features
- Local backend using FastAPI (Python)
- Frontend chat UI (Nextjs)
- Uses Ollama with Mistral 3 7b model
- Customizable system prompt for AI personality
- Mac compatible

## Setup
1. **Install Ollama**: https://ollama.com/download
2. **Pull the Mistral model**: `ollama pull mistral`
3. **Backend**: See `backend/README.md` for Python setup
4. **Frontend**: See `frontend/README.md` for setting up front end and open localhost:3000 in browser
5. **MCP**: Open `mcp/README.md` for setting up MCP server

## Development
- All code is in `backend/`, `frontend/`, and `mcp/` folders
- System prompt is in `backend/system_prompt.txt`

## License
MIT
