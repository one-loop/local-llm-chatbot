import os
import json
import requests

# --- Tool implementations ---
def get_menu():
    return ["Pizza", "Burger", "Salad"]

def get_open_restaurants():
    return ["West Dining Hall (D1)", "East Dining Hall (D2)", "Marketplace (C2)"]

def check_item(item):
    menu = get_menu()
    return item in menu

# --- Tool registry for dispatch ---
TOOL_REGISTRY = {
    "get_menu": get_menu,
    "get_open_restaurants": get_open_restaurants,
    "check_item": check_item,
}

# --- Tool schemas for prompt (JSON schema as string for system prompt) ---
tool_schemas = [
    {
        "name": "get_menu",
        "description": "Get the menu for the current day",
        "parameters": {},
    },
    {
        "name": "get_open_restaurants",
        "description": "Get a list of open restaurants",
        "parameters": {},
    },
    {
        "name": "check_item",
        "description": "Check if an item is on the menu",
        "parameters": {"item": "string (the item to check)"},
    },
]

# --- System prompt describing tool calling ---
system_prompt = (
    "You are a helpful assistant. You have access to the following tools, which you can call by outputting a JSON block with the tool name and arguments. "
    "Here are the available tools (in JSON):\n"
    + json.dumps(tool_schemas, indent=2)
    + "\nWhen the user asks something that requires a tool, respond ONLY with a JSON block like this: {\"tool\": \"tool_name\", \"arguments\": { ... }}. "
    "If no tool is needed, just answer normally."
)

final_answer_system_prompt = (
    "You are a helpful assistant. The user asked a question, and you called a tool to get the answer. "
    "Now, summarize the tool result for the user in clear, natural language. "
    "Do NOT output any JSON or tool call, just a helpful, concise answer."
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# --- Example prompts ---
prompts = [
    "What's the menu for today?",
    "Which restaurants are open?",
    "Is Pizza available?",
    "Hello, how are you today?",
]

def call_ollama(prompt, system_prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>\n",
        "stream": False
    }
    response = requests.post(OLLAMA_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("response", "")
    else:
        print(f"Ollama error: {response.text}")
        return ""

def try_parse_tool_call(text):
    """Try to parse a tool call from the model's response. Returns (tool_name, args_dict) or (None, None)."""
    try:
        # Find the first JSON object in the response
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != -1 and end > start:
            block = text[start:end]
            data = json.loads(block)
            tool = data.get("tool")
            args = data.get("arguments", {})
            return tool, args
    except Exception as e:
        pass
    return None, None

for prompt in prompts:
    print("\n===\nUser prompt:", prompt)
    # Step 1: Send to local Mistral (Ollama)
    model_response = call_ollama(prompt, system_prompt)
    print("Model response:", model_response)
    # Step 2: Check if model wants to call a tool
    tool, args = try_parse_tool_call(model_response)
    if tool:
        print(f"Model requested tool: {tool} with args: {args}")
        func = TOOL_REGISTRY.get(tool)
        if func:
            try:
                result = func(**args) if args else func()
            except Exception as e:
                result = f"Error running tool: {e}"
        else:
            result = "Unknown tool"
        print(f"Tool `{tool}` result: {result}")
        # Send the tool result back to the model for a final answer in natural language
        followup = (
            f"The user asked: {prompt}\n"
            f"The tool `{tool}` returned: {result}\n"
            "Please summarize this result for the user in natural language."
        )
        final_response = call_ollama(followup, final_answer_system_prompt)
        print("Final LLM answer:", final_response)
    else:
        print("Model direct answer:", model_response)
