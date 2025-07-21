import os
import json
import functools

# If you don't have mistralai, install it with:
# pip install mistralai
try:
    from mistralai import Mistral
except ImportError:
    raise ImportError("Please install mistralai: pip install mistralai")

# --- Tool implementations ---
def get_menu():
    return ["Pizza", "Burger", "Salad"]

def get_open_restaurants():
    return ["Cafe 1", "Diner 2", "Pizza Place"]

def check_item(item):
    menu = get_menu()
    return item in menu

# --- Tool registry for dispatch ---
TOOL_REGISTRY = {
    "get_menu": get_menu,
    "get_open_restaurants": get_open_restaurants,
    "check_item": check_item,
}

# --- Tool schemas for Mistral ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_menu",
            "description": "Get the menu for the current day",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_restaurants",
            "description": "Get a list of open restaurants",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_item",
            "description": "Check if an item is on the menu",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "The item to check on the menu."}
                },
                "required": ["item"],
            },
        },
    },
]

# --- Mistral API setup ---
api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    raise EnvironmentError("Please set the MISTRAL_API_KEY environment variable.")
model = "mistral-large-latest"  # Or your preferred function-calling model

client = Mistral(api_key=api_key)

# --- Example prompts ---
prompts = [
    "What's the menu for today?",
    "Which restaurants are open?",
    "Is Pizza available?",
    "Hello, how are you today?",
]

for prompt in prompts:
    print("\n===\nUser prompt:", prompt)
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.complete(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",  # Let the model decide if a tool is needed
        parallel_tool_calls=False,
    )
    choice = response.choices[0]
    msg = choice.message
    # If the model wants to call a tool, handle it
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tool_call in msg.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            print(f"Model requested tool: {function_name} with args: {function_args}")
            # Call the tool
            func = TOOL_REGISTRY.get(function_name)
            if func:
                try:
                    result = func(**function_args) if function_args else func()
                except Exception as e:
                    result = f"Error running tool: {e}"
            else:
                result = "Unknown tool"
            print(f"Tool `{function_name}` result: {result}")
            # Send tool result back to model for final answer
            tool_message = {
                "role": "tool",
                "name": function_name,
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            }
            messages.append(msg)
            messages.append(tool_message)
            # Get final answer
            final_response = client.chat.complete(
                model=model,
                messages=messages,
            )
            print("Final LLM answer:", final_response.choices[0].message.content)
    else:
        # No tool call, just print the model's direct response
        print("Model direct answer:", msg.content)
