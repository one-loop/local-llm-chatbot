# MCP Server

This directory contains the Menu Control Point (MCP) server, which provides menu and item endpoints for the chatbot backend.

## Requirements
- Python 3.8+
- pip (Python package manager)

## Setup Instructions

1. **(Optional) Create and activate a virtual environment:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Run the MCP server:**
   ```sh
   python main.py
   ```
   or (recommended for development):
   ```sh
   uvicorn main:app --reload --port 9000
   ```

The server will be available at `http://localhost:9000`.

## Troubleshooting
- If you see `ModuleNotFoundError`, make sure you have activated your virtual environment and installed all dependencies.
- If you need to install `uvicorn`, run:
  ```sh
  pip install uvicorn
  ``` 