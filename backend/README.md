# Backend - NYU Abu Dhabi Dining Hall Chatbot

## Requirements
- Python 3.8+
- [Ollama](https://ollama.com/) running locally (with the 'mistral' model pulled)

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

3. **Make sure Ollama is running and the 'mistral' model is available:**
   ```bash
   ollama pull qwen2.5
   ollama run qwen2.5
   ```

4. **Start the FastAPI server (on port 1000):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 1000
   ```
   The backend will be available at: http://localhost:1000

## System Prompt
- The system prompt is tailored for NYU Abu Dhabi Dining Hall support.
- Edit `system_prompt.txt` to further customize the assistant's persona or instructions.
- Restart the backend server to apply changes.

## Features
- **Streaming responses:** The backend streams the AI's response to the frontend as it is generated.
- **CORS enabled:** The backend is configured for local development with CORS support.

## Troubleshooting
- **Ollama errors:** Ensure Ollama is running and the 'mistral' model is pulled.
- **CORS errors:** CORS is enabled, but if you have issues, check your browser console and backend logs.
- **Python package errors:** Make sure your virtual environment is activated and all dependencies are installed.
- **Port conflicts:** Ensure no other service is running on port 1000.

## Notes
- The backend is designed to work with the Next.js frontend in the `frontend/` directory (which runs on port 3000).
- For further customization, edit the system prompt in `system_prompt.txt`.