# Frontend - NYU Abu Dhabi Dining Hall Chatbot

This is a Next.js app that provides a chat UI for interacting with the local dining hall chatbot backend.

## Requirements
- Node.js (v18+ recommended)
- The backend FastAPI server running on http://localhost:5000

## Setup

1. **Open a new terminal and navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   The app will be available at http://localhost:3000

## Usage
- Type a message or click a suggestion to start chatting with the dining hall assistant.
- The bot will respond in real time using the local LLM backend.
- Bot responses support markdown formatting and code highlighting.

## Notes
- Make sure the backend is running and accessible at http://localhost:5000
- The backend system prompt/persona can be customized in `backend/system_prompt.txt`.

## Troubleshooting
- **Cannot connect to backend:** Make sure the backend is running on port 5000.
- **CORS errors:** CORS is enabled in the backend, but check your browser console and backend logs if you have issues.
- **npm errors about missing package.json:** Make sure you are in the correct `frontend` directory.
- **Markdown/code not formatted:** Ensure all dependencies are installed (`react-markdown`, `react-syntax-highlighter`).
