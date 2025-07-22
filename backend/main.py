import os
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import json
import re
import datetime
from typing import Dict, Optional, List

# Import our background order system
from background_order_system import (
    ConversationLogger, OrderKeywordDetector, BackgroundOrderProcessor
)
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

# Final order storage path
ORDERS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'orders.txt'))

# Available buildings
AVAILABLE_BUILDINGS = ["A1A", "A1B", "A1C", "A2A", "A2B", "A2C", "A3", "A4", "A5A", "A5B", "A5C", "A6A", "A6B", "A6C"]

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

def save_final_order_to_file(order_data: Dict):
    """Save completed order to final orders file"""
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
            
            f.write(f"NYU ID: N{order_data.get('nyu_id', 'N/A')}\n")
            f.write(f"Building: {order_data.get('building', 'N/A')}\n")
            f.write(f"Phone: {order_data.get('phone', 'N/A')}\n")
            f.write(f"Special Request: {order_data.get('special_request', 'None')}\n")
            f.write("=" * 50 + "\n")
            
        print(f"DEBUG: Saved final order to file")
        
    except Exception as e:
        print(f"Error saving order: {e}")

def extract_order_completion_data(conversation: List[Dict]) -> Optional[Dict]:
    """Extract order completion data from conversation history"""
    
    user_messages = []
    
    for msg in conversation:
        if msg['sender'] == 'user':
            user_messages.append(msg['message'])
    
    # Combine all user messages for analysis
    combined_text = " ".join(user_messages)
    
    # Extract order information
    items = rag_extract_menu_items(combined_text)
    if not items:
        return None
    
    # Extract NYU ID (8 digits) - must be explicitly provided
    nyu_id_match = re.search(r'\b(\d{8})\b', combined_text)
    nyu_id = nyu_id_match.group(1) if nyu_id_match else None
    
    # Extract building (A1A, A2B, etc.) - must be explicitly provided
    building_match = re.search(r'\b(A\d[ABC])\b', combined_text, re.IGNORECASE)
    building = building_match.group(1).upper() if building_match else None
    
    # Extract phone (9-15 digits) - must be explicitly provided
    phone_match = re.search(r'\b(\d{9,15})\b', combined_text.replace(' ', '').replace('-', ''))
    phone = phone_match.group(1) if phone_match else None
    
    # Extract special requests (look for patterns after "special", "request", "note", etc.)
    special_request = "None"
    for msg in reversed(user_messages[-5:]):  # Look at last 5 messages
        if any(keyword in msg.lower() for keyword in ['special', 'request', 'note', 'dietary', 'allergy']):
            if not any(word in msg.lower() for word in ['no', 'none', 'nothing']):
                special_request = msg
                break
    
    # CRITICAL: Only complete order if ALL required fields are present
    if not (items and nyu_id and building and phone):
        print(f"DEBUG: Order incomplete - Items: {bool(items)}, NYU ID: {bool(nyu_id)}, Building: {bool(building)}, Phone: {bool(phone)}")
        return None
    
    print(f"DEBUG: Order completion requirements met - NYU ID: {nyu_id}, Building: {building}, Phone: {phone}")
    
    total_cost = sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items)
    
    return {
        'items': items,
        'total_cost': total_cost,
        'nyu_id': nyu_id,
        'building': building,
        'phone': phone,
        'special_request': special_request
    }

def check_for_order_completion(session_id: str) -> Optional[str]:
    """Check if an order can be completed and return confirmation message"""
    
    conversation = ConversationLogger.get_conversation(session_id)
    if len(conversation) < 6:  # Need reasonable conversation for complete order
        return None
    
    # Extract order data from entire conversation
    order_data = extract_order_completion_data(conversation)
    if not order_data:
        return None
    
    # Verify building is valid
    if order_data['building'] not in AVAILABLE_BUILDINGS:
        return None
    
    # Save the completed order
    save_final_order_to_file(order_data)
    
    # Format confirmation message
    items_list = []
    for item in order_data['items']:
        qty = item.get('quantity', 1)
        if qty > 1:
            items_list.append(f"{qty}x {item['name']}")
        else:
            items_list.append(item['name'])
    
    items_text = ", ".join(items_list)
    
    # Clean up session files after successful order
    ConversationLogger.cleanup_session(session_id)
    
    confirmation = f"✅ Order confirmed! Items: {items_text}. Total: AED {order_data['total_cost']:.2f}. NYU ID: N{order_data['nyu_id']}, Building: {order_data['building']}, Phone: {order_data['phone']}. Special Request: {order_data['special_request']}."
    
    print(f"DEBUG: Order completed for session {session_id}")
    return confirmation

def check_for_direct_order_response(session_id: str, user_message: str) -> Optional[str]:
    """Check if we should give a direct order response instead of using AI"""
    
    detected_order = OrderKeywordDetector.get_detected_order(session_id)
    if not detected_order:
        return None
    
    items = detected_order.get('items', [])
    stage = detected_order.get('stage', 'order_intent')
    total_cost = detected_order.get('total_cost', 0)
    
    if not items:
        return None
    
    # Format items for display
    items_text = ", ".join([f"{item.get('quantity', 1)}x {item.get('name', 'Unknown')}" for item in items])
    
    user_message_lower = user_message.lower().strip()
    
    print(f"DEBUG: Checking direct response - Stage: {stage}, Message: '{user_message}'")
    
    # Direct responses based on stage
    if stage == "confirming_order":
        if re.search(r'\b(yes|yeah|yep|confirm|ok|okay|sure|correct|right|proceed)\b', user_message_lower):
            return f"Great! To complete your order for {items_text} (AED {total_cost:.2f}), I need your NYU ID. Please provide the 8 digits after the N (e.g., if your ID is N12345678, enter 12345678):"
    
    elif stage == "nyu_id_provided":
        return f"Perfect! Now please select your building number from the following options: A1A, A1B, A1C, A2A, A2B, A2C, A3, A4, A5A, A5B, A5C, A6A, A6B, A6C"
    
    elif stage == "building_provided":
        return f"Great! Now please provide your phone number:"
    
    elif stage == "phone_provided":
        return f"Do you have any special requests for your order? (e.g., extra toppings, dietary restrictions, etc.) If not, just say 'no' or 'none':"
    
    return None

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

@app.post('/chat')
async def chat_endpoint(request: Request, background_tasks: BackgroundTasks):
    """
    Main chat endpoint with background order detection and direct responses
    """
    # Parse the incoming JSON
    try:
        body = await request.json()
        user_message = body["message"]
        history = body.get("history", [])
        session_id = body.get("session_id", "default")
        print(f"DEBUG: Chat endpoint - session_id: {session_id}, message: '{user_message}'")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    # Log the user message to conversation file
    ConversationLogger.log_message(session_id, user_message, "user")
    
    # Process background order detection IMMEDIATELY
    await BackgroundOrderProcessor.process_session_orders(session_id)
    
    # Check for direct order response FIRST (highest priority)
    direct_response = check_for_direct_order_response(session_id, user_message)
    if direct_response:
        print(f"DEBUG: Direct order response: {direct_response}")
        
        async def direct_response_stream():
            yield direct_response
        
        # Log bot response
        ConversationLogger.log_message(session_id, direct_response, "bot")
        return StreamingResponse(direct_response_stream(), media_type="text/plain")
    
    # Check for order completion second
    order_completion = check_for_order_completion(session_id)
    if order_completion:
        print(f"DEBUG: Order completion detected: {order_completion}")
        
        async def completion_response_stream():
            yield order_completion
        
        # Log bot response
        ConversationLogger.log_message(session_id, order_completion, "bot")
        return StreamingResponse(completion_response_stream(), media_type="text/plain")

    # Continue with normal AI chat
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
        
        # RAG-based multiple item extraction for immediate responses
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
                
                # Check for order intent
                if re.search(r'order|buy|get|want|purchase|can i get|i\'?ll have', user_message, re.IGNORECASE):
                    total_cost = sum(item['total_price'] for item in found_items)
                    order_context = f"\n[IMMEDIATE ORDER] User wants to order: {items_summary} (Total: AED {total_cost:.2f}). Ask them to confirm this order by saying 'yes'."
            
            if not_found_items:
                not_found_text = ", ".join(not_found_items)
                if menu_items_context:
                    menu_items_context += f"\n\nItems not found: {not_found_text}"
                else:
                    menu_items_context = f"Sorry, these items are not on the menu: {not_found_text}"

        # Get menu context for full menu requests
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

        # Collect the bot response for logging
        bot_response = ""
        
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                chunk = data["response"]
                                bot_response += chunk
                                yield chunk
                        except Exception as e:
                            print(f"Streaming parse error: {e}")
            except Exception as e:
                print(f"Ollama streaming error: {e}")
                error_msg = "[Error streaming from Ollama]"
                bot_response = error_msg
                yield error_msg
        
        # Log the bot response after streaming is complete
        if bot_response:
            ConversationLogger.log_message(session_id, bot_response, "bot")

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

# Debug endpoints
@app.get('/debug/conversation/{session_id}')
def debug_conversation(session_id: str):
    """Debug endpoint to view conversation history"""
    conversation = ConversationLogger.get_conversation(session_id)
    return {
        "session_id": session_id,
        "conversation": conversation,
        "message_count": len(conversation)
    }

@app.get('/debug/order/{session_id}')
def debug_detected_order(session_id: str):
    """Debug endpoint to view detected order"""
    detected_order = OrderKeywordDetector.get_detected_order(session_id)
    
    return {
        "session_id": session_id,
        "detected_order": detected_order,
        "has_order": detected_order is not None
    }

@app.post('/debug/force_order_completion/{session_id}')
def debug_force_completion(session_id: str):
    """Debug endpoint to force order completion check"""
    completion_message = check_for_order_completion(session_id)
    return {
        "session_id": session_id,
        "completion_message": completion_message,
        "completed": completion_message is not None
    }

@app.post('/debug/cleanup_session/{session_id}')
def debug_cleanup_session(session_id: str):
    """Debug endpoint to manually cleanup session files"""
    ConversationLogger.cleanup_session(session_id)
    return {
        "session_id": session_id,
        "status": "cleaned_up"
    }

@app.post('/debug/test_direct_response/{session_id}')
def test_direct_response(session_id: str):
    """Debug endpoint to test direct response system"""
    
    # Setup test order
    test_order = {
        "items": [{"name": "Chicken Wings", "quantity": 5, "price": 23.0, "total_price": 115.0}],
        "stage": "confirming_order",
        "total_cost": 115.0,
        "detected_at": datetime.datetime.now().isoformat(),
        "conversation_length": 5
    }
    
    OrderKeywordDetector.save_detected_order(session_id, test_order)
    
    # Test various messages
    test_messages = [
        "yes",
        "12345678",
        "A1A",
        "971501234567",
        "no special requests"
    ]
    
    results = []
    for message in test_messages:
        # Simulate stage progression
        if message == "yes":
            test_order["stage"] = "confirming_order"
        elif message == "12345678":
            test_order["stage"] = "nyu_id_provided"
        elif message == "A1A":
            test_order["stage"] = "building_provided"
        elif message == "971501234567":
            test_order["stage"] = "phone_provided"
        
        OrderKeywordDetector.save_detected_order(session_id, test_order)
        
        direct_response = check_for_direct_order_response(session_id, message)
        results.append({
            "message": message,
            "stage": test_order["stage"],
            "direct_response": direct_response,
            "has_response": direct_response is not None
        })
    
    # Cleanup
    ConversationLogger.cleanup_session(session_id)
    
    return {
        "test": "direct_response_system",
        "results": results
    }

@app.get('/debug/active_sessions')
def debug_active_sessions():
    """Debug endpoint to list active conversation sessions"""
    conversations_dir = os.path.join(os.path.dirname(__file__), 'conversations')
    temp_orders_dir = os.path.join(os.path.dirname(__file__), 'temp_orders')
    
    active_sessions = []
    
    # Check conversation files
    if os.path.exists(conversations_dir):
        for file in os.listdir(conversations_dir):
            if file.startswith('conversation_') and file.endswith('.json'):
                session_id = file.replace('conversation_', '').replace('.json', '')
                active_sessions.append(session_id)
    
    return {
        "active_sessions": active_sessions,
        "count": len(active_sessions),
        "conversations_dir": conversations_dir,
        "temp_orders_dir": temp_orders_dir
    }