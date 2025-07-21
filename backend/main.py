import os
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import json
import re
import datetime
from typing import Dict, Optional, List
from menu_embeddings import rag_extract_menu_items, rag_extract_menu_item, format_items_summary

# Define the path to the system prompt file
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt.txt')

# Ollama API endpoint (assumes Ollama is running locally)
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'mistral'

# MCP server endpoints
MCP_ITEM_URL = 'http://localhost:9000/menu/item'
MCP_MENU_URL = 'http://localhost:9000/menu/today'

RESTAURANTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'restaurants.json'))

# Order storage path
ORDERS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'orders.txt'))

# Available buildings
AVAILABLE_BUILDINGS = ["A1A", "A1B", "A1C", "A2A", "A2B", "A2C", "A3", "A4", "A5A", "A5B", "A5C", "A6A", "A6B", "A6C"]

# In-memory order state (in production, use a proper database)
order_states: Dict[str, Dict] = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

def save_order_to_file(order_data: Dict):
    """Save order to text file"""
    try:
        with open(ORDERS_PATH, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n=== ORDER - {timestamp} ===\n")
            
            # Handle multiple items
            if 'items' in order_data:
                f.write("ITEMS:\n")
                total_cost = 0
                for item in order_data['items']:
                    qty = item.get('quantity', 1)
                    price = item.get('price', 0)
                    total_price = item.get('total_price', price * qty)
                    total_cost += total_price
                    f.write(f"- {qty}x {item['name']}: AED {price} each = AED {total_price}\n")
                f.write(f"TOTAL COST: AED {total_cost:.2f}\n")
            else:
                # Backwards compatibility for single item
                f.write(f"Item: {order_data['item_name']}\n")
                f.write(f"Price: AED {order_data['price']}\n")
            
            f.write(f"NYU ID: N{order_data['nyu_id']}\n")
            f.write(f"Building: {order_data['building']}\n")
            f.write(f"Phone: {order_data['phone']}\n")
            f.write(f"Special Request: {order_data.get('special_request', 'None')}\n")
            f.write("=" * 50 + "\n")
    except Exception as e:
        print(f"Error saving order: {e}")

def get_order_state(session_id: str) -> Dict:
    """Get or create order state for a session"""
    if session_id not in order_states:
        order_states[session_id] = {
            'state': 'idle',
            'items': [],  # Changed to support multiple items
            'total_cost': 0,
            'nyu_id': None,
            'building': None,
            'phone': None,
            'special_request': None
        }
    return order_states[session_id]

def reset_order_state(session_id: str):
    """Reset order state for a session"""
    if session_id in order_states:
        order_states[session_id] = {
            'state': 'idle',
            'items': [],
            'total_cost': 0,
            'nyu_id': None,
            'building': None,
            'phone': None,
            'special_request': None
        }

def calculate_total_cost(items: List[Dict]) -> float:
    """Calculate total cost of all items"""
    return sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items)

async def fetch_menu_item_from_mcp(item_name: str):
    """Query the MCP server for a menu item by name."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(MCP_ITEM_URL, params={"name": item_name}, timeout=2)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
    except Exception as e:
        print(f"Error fetching menu item from MCP: {e}")
        return None

async def fetch_full_menu_from_mcp():
    """Query the MCP server for the full menu."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(MCP_MENU_URL, timeout=2)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
    except Exception as e:
        print(f"Error fetching full menu from MCP: {e}")
        return None

def get_open_restaurants():
    now = datetime.datetime.now().time()
    try:
        with open(RESTAURANTS_PATH, 'r') as f:
            data = json.load(f)
        open_list = []
        for r in data:
            open_time = datetime.datetime.strptime(r['open'], '%H:%M').time()
            close_time = datetime.datetime.strptime(r['close'], '%H:%M').time()
            if open_time <= now <= close_time:
                open_list.append(f"{r['name']} (Open: {r['open']} - {r['close']})")
        return open_list
    except Exception as e:
        print(f"Error loading restaurants.json: {e}")
        return None

def process_order_flow(user_message: str, session_id: str) -> tuple[str, bool]:
    """
    Process the order flow and return a response message and whether to continue with normal chat
    Returns: (response_message, continue_with_normal_chat)
    """
    order_state = get_order_state(session_id)
    user_message_lower = user_message.lower().strip()
    
    # Check if user wants to start ordering or add more items
    if order_state['state'] == 'idle':
        # Try to extract multiple items
        items_data = rag_extract_menu_items(user_message)
        if items_data:
            # This will be handled in the main chat flow
            return "", True
    
    # Check if user wants to add more items during order confirmation
    elif order_state['state'] == 'waiting_for_order_confirmation':
        if 'add' in user_message_lower or 'more' in user_message_lower:
            # Try to extract additional items
            additional_items = rag_extract_menu_items(user_message)
            if additional_items:
                order_state['items'].extend(additional_items)
                order_state['total_cost'] = calculate_total_cost(order_state['items'])
                items_summary = format_items_summary(order_state['items'])
                return f"Added to your order! Your current order:\n\n{items_summary}\n\nWould you like to confirm this order or add more items?", False
            else:
                return "I couldn't find those items on the menu. Would you like to confirm your current order or try adding different items?", False
        
        elif 'yes' in user_message_lower or 'confirm' in user_message_lower:
            order_state['state'] = 'waiting_for_nyu_id'
            return "Great! Please provide the 8 digits of your NYU ID card after the N (e.g., if your ID is N12345678, enter 12345678):", False
        elif 'no' in user_message_lower or 'cancel' in user_message_lower:
            reset_order_state(session_id)
            return "Order cancelled. How else can I help you today?", False
        else:
            items_summary = format_items_summary(order_state['items'])
            return f"Your current order:\n\n{items_summary}\n\nPlease respond with 'yes' to confirm, 'no' to cancel, or tell me what you'd like to add.", False
    
    elif order_state['state'] == 'waiting_for_nyu_id':
        # Validate NYU ID (8 digits)
        nyu_id_match = re.search(r'(\d{8})', user_message)
        if nyu_id_match:
            order_state['nyu_id'] = nyu_id_match.group(1)
            order_state['state'] = 'waiting_for_building'
            buildings_list = ", ".join(AVAILABLE_BUILDINGS)
            return f"Perfect! Now please select your building number from the following options: {buildings_list}", False
        else:
            return "Please enter exactly 8 digits of your NYU ID (e.g., 12345678):", False
    
    elif order_state['state'] == 'waiting_for_building':
        building = user_message.strip().upper()
        if building in AVAILABLE_BUILDINGS:
            order_state['building'] = building
            order_state['state'] = 'waiting_for_phone'
            return "Great! Now please provide your phone number:", False
        else:
            buildings_list = ", ".join(AVAILABLE_BUILDINGS)
            return f"Please select a valid building from: {buildings_list}", False
    
    elif order_state['state'] == 'waiting_for_phone':
        # Basic phone validation
        phone_match = re.search(r'(\d{9,15})', user_message.replace(' ', '').replace('-', '').replace('+', ''))
        if phone_match:
            order_state['phone'] = phone_match.group(1)
            order_state['state'] = 'waiting_for_special_request'
            return "Do you have any special requests for your order? (e.g., extra toppings, dietary restrictions, etc.) If not, just say 'no' or 'none':", False
        else:
            return "Please provide a valid phone number:", False
    
    elif order_state['state'] == 'waiting_for_special_request':
        if user_message_lower in ['no', 'none', 'n/a', 'no special requests']:
            order_state['special_request'] = 'None'
        else:
            order_state['special_request'] = user_message
        
        # Complete the order
        order_data = {
            'items': order_state['items'],
            'total_cost': order_state['total_cost'],
            'nyu_id': order_state['nyu_id'],
            'building': order_state['building'],
            'phone': order_state['phone'],
            'special_request': order_state['special_request']
        }
        
        # Save order to file
        save_order_to_file(order_data)
        
        # Format confirmation message
        items_list = []
        for item in order_state['items']:
            qty = item.get('quantity', 1)
            if qty > 1:
                items_list.append(f"{qty}x {item['name']}")
            else:
                items_list.append(item['name'])
        
        items_text = ", ".join(items_list)
        
        # Reset order state
        reset_order_state(session_id)
        
        confirmation_message = f"✅ Order confirmed for: {items_text}. Total: AED {order_data['total_cost']:.2f}. NYU ID: N{order_data['nyu_id']}, Building: {order_data['building']}, Phone: {order_data['phone']}. Special Request: {order_data['special_request']}."
        return confirmation_message, False
    
    return "", True

@app.post('/chat')
async def chat_endpoint(request: Request):
    """
    Streams the AI's response as it is generated by Ollama.
    If the user asks about a menu item or the full menu, query the MCP server and include the result in the prompt.
    """
    # Parse the incoming JSON
    try:
        body = await request.json()
        user_message = body["message"]
        history = body.get("history", [])
        session_id = body.get("session_id", "default")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    # Check if we're in an order flow
    order_response, continue_normal_chat = process_order_flow(user_message, session_id)
    if order_response:
        # Return the order flow response directly
        async def order_response_stream():
            yield order_response
        return StreamingResponse(order_response_stream(), media_type="text/plain")

    # Load the system prompt
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            system_prompt = f.read().strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load system prompt: {e}")

    async def ollama_stream():
        # Check if the user is asking for the full menu
        if re.search(r"what'?s on the menu|show me the menu|today'?s menu|full menu", user_message, re.IGNORECASE):
            yield "[Fetching menu data...]\n"
        
        # RAG-based multiple item extraction
        items_data = rag_extract_menu_items(user_message)
        menu_items_context = ""
        order_context = ""

        if items_data:
            found_items = []
            not_found_items = []
            
            for item_data in items_data:
                item_name = item_data["name"]
                yield f"[Looking up '{item_name}' in the menu...]\n"
                
                # Verify with MCP server
                item = await fetch_menu_item_from_mcp(item_name)
                if item:
                    # Update with verified data from MCP
                    verified_item = {
                        'name': item['name'],
                        'price': item['price'],
                        'quantity': item_data.get('quantity', 1)
                    }
                    verified_item['total_price'] = verified_item['price'] * verified_item['quantity']
                    found_items.append(verified_item)
                else:
                    not_found_items.append(item_data['name'])
            
            if found_items:
                items_summary = format_items_summary(found_items)
                menu_items_context = f"Menu items found:\n{items_summary}"
                
                # Check if user wants to order these items
                if re.search(r'order|buy|get|want to order|purchase', user_message, re.IGNORECASE):
                    order_state = get_order_state(session_id)
                    order_state['state'] = 'waiting_for_order_confirmation'
                    order_state['items'] = found_items
                    order_state['total_cost'] = calculate_total_cost(found_items)
                    order_context = f"\n[ORDER FLOW] The user wants to order multiple items. Ask them to confirm their order by responding with 'yes' or 'no'. They can also add more items."
            
            if not_found_items:
                not_found_text = ", ".join(not_found_items)
                if menu_items_context:
                    menu_items_context += f"\n\nItems not found: {not_found_text}"
                else:
                    menu_items_context = f"Sorry, these items are not on the menu: {not_found_text}"

        # Rest of the existing code for menu context, open restaurants, etc.
        menu_context = ""
        if re.search(r"what'?s on the menu|show me the menu|today'?s menu|full menu|what'?s available|what'?s available today", user_message, re.IGNORECASE):
            menu = await fetch_full_menu_from_mcp()
            if menu:
                menu_context = "[TOOL] MCP server response:\n"
                for item in menu:
                    menu_context += f"- {item['name']}: AED {item['price']}\n"
            else:
                menu_context = "[Menu data is currently unavailable.]"

        # Check if the user is asking about open restaurants
        open_restaurants_context = ""
        if re.search(r"what'?s open|which restaurants are open|open now|open restaurants", user_message, re.IGNORECASE):
            yield "[Checking which restaurants are open... Please wait.]\n"
            open_list = get_open_restaurants()
            if open_list is not None:
                if open_list:
                    open_restaurants_context = "[TOOL] Open restaurants right now:\n" + "\n".join(f"- {r}" for r in open_list)
                else:
                    open_restaurants_context = "[TOOL] No restaurants are currently open."
            else:
                open_restaurants_context = "[Restaurant data is currently unavailable.]"

        # Build the conversation history prompt
        history_prompt = ""
        for msg in history:
            if msg.get("sender") == "user":
                history_prompt += f"User: {msg['text']}\n"
            elif msg.get("sender") == "bot":
                history_prompt += f"Assistant: {msg['text']}\n"

        # Prepare the payload for Ollama
        prompt = system_prompt
        if menu_context:
            prompt += f"\n\n{menu_context}"
        if menu_items_context:
            prompt += f"\n\nMenu info: {menu_items_context}"
        if order_context:
            prompt += f"\n\n{order_context}"
        if open_restaurants_context:
            prompt += f"\n\n{open_restaurants_context}"
        prompt += f"\n{history_prompt}User: {user_message}\nAssistant:"

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except Exception as e:
                            print(f"Streaming parse error: {e}")
            except Exception as e:
                print(f"Ollama streaming error: {e}")
                yield "[Error streaming from Ollama]"

    return StreamingResponse(ollama_stream(), media_type="text/plain")

@app.get('/warmup')
def warmup():
    """
    Endpoint to warm up the Ollama model by sending a dummy request.
    """
    import requests
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": "Hello!",
            "stream": False
        }
        # Send a dummy request to Ollama to trigger model load
        r = requests.post(OLLAMA_URL, json=payload, timeout=10)
        if r.status_code == 200:
            return {"status": "warmed up"}
        else:
            return Response(content=f"Ollama error: {r.text}", status_code=500)
    except Exception as e:
        return Response(content=f"Warmup error: {e}", status_code=500)