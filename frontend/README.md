# Frontend - Local LLM Chatbot

This is a simple Next.js app that provides a chat UI for interacting with the local LLM backend.

## Requirements
- Node.js (v18+ recommended)
- The backend FastAPI server running on http://localhost:5000

## Setup

1. **Open a new terminal and navigate to the frontend directory:**
   ```bash
   cd /path/to/local-llm-chatbot/frontend
   # or, if you're already in the project root:
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
- Type a message and press Enter or click Send.
- The bot will respond using the local LLM backend.

## Notes
- Make sure the backend is running and accessible at http://localhost:5000
- Always run frontend commands inside the `local-llm-chatbot/frontend` directory.

## Troubleshooting
- **Cannot connect to backend:** Make sure the backend is running on port 5000.
- **CORS errors:** See backend README for enabling CORS support.
- **npm errors about missing package.json:** Make sure you are in the correct `frontend` directory.
