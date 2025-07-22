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
        # FIX: Use 'a' mode to append, not 'w' which overwrites
        with open(ORDERS_PATH, 'w', encoding='utf-8') as f:
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
    """Extract order completion data from conversation history with change detection"""
    
    user_messages = []
    bot_messages = []
    
    for msg in conversation:
        if msg['sender'] == 'user':
            user_messages.append(msg['message'])
        else:
            bot_messages.append(msg['message'])
    
    # SMART ORDER EXTRACTION: Analyze conversation chronologically for changes
    final_items = {}  # Dict to track latest quantity for each item
    
    print(f"DEBUG: Analyzing {len(user_messages)} user messages for order changes")
    
    # Process each user message chronologically to detect changes
    for i, message in enumerate(user_messages):
        message_items = rag_extract_menu_items(message)
        
        if message_items:
            print(f"DEBUG: Message {i+1}: '{message}' -> Found items: {message_items}")
            
            # Check for change indicators
            is_change = any(word in message.lower() for word in [
                'actually', 'instead', 'change', 'make it', 'i want', 'no wait', 
                'sorry', 'correction', 'modify', 'update', 'rather'
            ])
            
            for item in message_items:
                item_name = item['name']
                item_quantity = item.get('quantity', 1)
                
                if is_change:
                    print(f"DEBUG: CHANGE DETECTED - Updating {item_name} to {item_quantity}")
                    # If this is a change, replace the previous quantity
                    final_items[item_name] = item
                elif item_name in final_items:
                    # If item already exists, check if this is an addition or replacement
                    if any(word in message.lower() for word in ['more', 'also', 'add', 'plus', 'and']):
                        # This is an addition
                        old_qty = final_items[item_name]['quantity']
                        new_qty = old_qty + item_quantity
                        print(f"DEBUG: ADDITION - {item_name}: {old_qty} + {item_quantity} = {new_qty}")
                        final_items[item_name]['quantity'] = new_qty
                        final_items[item_name]['total_price'] = final_items[item_name]['price'] * new_qty
                    else:
                        # This is likely a replacement/update
                        print(f"DEBUG: REPLACEMENT - {item_name}: {final_items[item_name]['quantity']} -> {item_quantity}")
                        final_items[item_name] = item
                else:
                    # New item
                    print(f"DEBUG: NEW ITEM - {item_name}: {item_quantity}")
                    final_items[item_name] = item
    
    # Convert back to list format
    items = list(final_items.values()) if final_items else None
    
    if items:
        print(f"DEBUG: FINAL ORDER ITEMS: {items}")
    
    # Combine all user messages for other data extraction
    combined_text = " ".join(user_messages)
    
    # Extract NYU ID - Must be EXACTLY 8 digits
    nyu_id = None
    valid_nyu_id = False
    # Look for any sequence of digits
    nyu_id_matches = re.finditer(r'\b\d+\b', combined_text)
    for match in nyu_id_matches:
        potential_id = match.group(0)
        # Check if it's exactly 8 digits
        if len(potential_id) == 8:
            nyu_id = potential_id
            valid_nyu_id = True
            break
    
    # Extract building - Must be in AVAILABLE_BUILDINGS list
    building = None
    valid_building = False
    # Look for building patterns (case insensitive)
    building_matches = re.finditer(r'\b[Aa]\d[ABCabc]\b', combined_text)
    for match in building_matches:
        potential_building = match.group(0).upper()
        if potential_building in AVAILABLE_BUILDINGS:
            building = potential_building
            valid_building = True
            break
    
    # Extract phone number - Must be 9-15 digits
    phone = None
    valid_phone = False
    # First, try to find any sequence of digits (ignoring spaces, dashes, etc.)
    phone_matches = re.finditer(r'\b\d[\d\s-]{7,13}\d\b', combined_text)
    for match in phone_matches:
        # Clean the number (remove spaces and dashes)
        potential_phone = re.sub(r'[\s-]', '', match.group(0))
        # Check if the cleaned number is between 9 and 15 digits
        if 9 <= len(potential_phone) <= 15:
            phone = potential_phone
            valid_phone = True
            break
    
    # Extract special requests - Look at most recent relevant messages
    special_request = "None"
    for msg in reversed(user_messages[-10:]):  # Look at last 10 messages for more context
        if any(keyword in msg.lower() for keyword in ['special', 'request', 'note', 'dietary', 'allergy']):
            if not any(word in msg.lower() for word in ['no', 'none', 'nothing']):
                special_request = msg
                break
    
    # Check if we have all required fields
    has_all_fields = (items and valid_nyu_id and valid_building and valid_phone)
    
    # If we have any order data, return it along with status
    if items:
        order_data = {
            'items': items,
            'total_cost': sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items),
            'nyu_id': nyu_id,
            'building': building,
            'phone': phone,
            'special_request': special_request,
            'is_complete': has_all_fields,
            'valid_building': valid_building,
            'valid_phone': valid_phone,
            'valid_nyu_id': valid_nyu_id
        }
        
        # Add missing fields list for context
        missing_fields = []
        if not valid_nyu_id:
            missing_fields.append('nyu_id')
        if not valid_building:
            missing_fields.append('building')
        if not valid_phone:
            missing_fields.append('phone')
        
        order_data['missing_fields'] = missing_fields
        return order_data
    
    return None

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
    
    # Only handle explicit cancellations here
    if stage == "confirming_order":
        if re.search(r'\b(no|nah|nope|cancel|wrong|incorrect)\b', user_message_lower):
            OrderKeywordDetector.save_detected_order(session_id, None)
            return None  # Let the LLM handle the response naturally
    
    return None

def check_for_order_completion(session_id: str) -> Optional[str]:
    """Check if an order can be completed and return confirmation message"""
    
    conversation = ConversationLogger.get_conversation(session_id)
    if len(conversation) < 3:  # Need at least some conversation
        return None
    
    # Extract order data from entire conversation
    order_data = extract_order_completion_data(conversation)
    if not order_data:
        return None
    
    # FIX: Actually complete the order if we have all valid information
    if order_data.get('is_complete') and order_data.get('valid_building'):
        # Format items for display
        items_list = []
        for item in order_data['items']:
            qty = item.get('quantity', 1)
            if qty > 1:
                items_list.append(f"{qty}x {item['name']}")
            else:
                items_list.append(item['name'])
        
        items_text = ", ".join(items_list)
        
        # Save the completed order
        save_final_order_to_file(order_data)
        
        # Clean up session files after successful order
        ConversationLogger.cleanup_session(session_id)
        
        # FIX: Return the actual completion message instead of None
        confirmation = f"✅ Order confirmed! Items: {items_text}. Total: AED {order_data['total_cost']:.2f}. NYU ID: N{order_data['nyu_id']}, Building: {order_data['building']}, Phone: {order_data['phone']}. Special Request: {order_data['special_request']}. Your order has been placed successfully!"
        
        print(f"DEBUG: Order completed for session {session_id}")
        return confirmation
    
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
    Main chat endpoint with background order detection and LLM-driven responses
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
    
    # Process background order detection
    await BackgroundOrderProcessor.process_session_orders(session_id)
    
    # Check for explicit order cancellation
    direct_response = check_for_direct_order_response(session_id, user_message)
    if direct_response:
        async def direct_response_stream():
            yield direct_response
        
        ConversationLogger.log_message(session_id, direct_response, "bot")
        return StreamingResponse(direct_response_stream(), media_type="text/plain")
    
    # Extract current order state
    order_data = extract_order_completion_data(ConversationLogger.get_conversation(session_id))
    
    # FIX: Check for order completion and actually return the message
    completion_message = check_for_order_completion(session_id)
    if completion_message:
        async def completion_response_stream():
            yield completion_message
        
        ConversationLogger.log_message(session_id, completion_message, "bot")
        return StreamingResponse(completion_response_stream(), media_type="text/plain")

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
                    order_context = f"\n[ORDER CONTEXT] User wants to order: {items_summary} (Total: AED {total_cost:.2f})."
            
            if not_found_items:
                not_found_text = ", ".join(not_found_items)
                if menu_items_context:
                    menu_items_context += f"\n\nItems not found: {not_found_text}"
                else:
                    menu_items_context = f"Items not found: {not_found_text}"

        # Get menu context for full menu requests
        menu_context = ""
        if re.search(r"what'?s on the menu|show me the menu|today'?s menu|full menu|what'?s available|what'?s available today", user_message, re.IGNORECASE):
            menu = await fetch_full_menu_from_mcp()
            if menu:
                menu_context = "[MENU DATA]:\n"
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
                    open_restaurants_context = "[OPEN RESTAURANTS]:\n" + "\n".join(f"- {r}" for r in open_list)
                else:
                    open_restaurants_context = "[No restaurants are currently open.]"
            else:
                open_restaurants_context = "[Restaurant data is currently unavailable.]"

        # Add order status context if there's an active order
        order_status_context = ""
        if order_data:
            missing_fields = order_data.get('missing_fields', [])
            order_status_context = "\n[[ORDER STATUS]]\n"
            if order_data['items']:
                items_text = ", ".join([f"{item.get('quantity', 1)}x {item['name']}" for item in order_data['items']])
                order_status_context += f"Current order (analyzed from entire conversation): {items_text} (Total: AED {order_data['total_cost']:.2f})\n"
                
                # Check if this looks like the user made changes by checking conversation
                conversation = ConversationLogger.get_conversation(session_id)
                user_messages_with_items = []
                for msg in conversation:
                    if msg['sender'] == 'user' and rag_extract_menu_items(msg['message']):
                        user_messages_with_items.append(msg['message'])
                        
                if len(user_messages_with_items) > 1:
                    order_status_context += "Note: User may have made changes to their order during conversation.\n"
                    
            if missing_fields:
                order_status_context += "Still needed:\n"
                if 'nyu_id' in missing_fields:
                    order_status_context += "- NYU ID (8 digits)\n"
                    if order_data.get('nyu_id'):
                        order_status_context += "[INVALID NYU ID PROVIDED - Must be exactly 8 digits]\n"
                if 'building' in missing_fields:
                    order_status_context += f"- Valid building number (options: {', '.join(AVAILABLE_BUILDINGS)})\n"
                    if order_data.get('building'):
                        order_status_context += "[INVALID BUILDING PROVIDED - Must be one of the valid options]\n"
                if 'phone' in missing_fields:
                    order_status_context += "- Phone number (9-15 digits)\n"
                    if order_data.get('phone'):
                        order_status_context += "[INVALID PHONE NUMBER PROVIDED - Must be between 9 and 15 digits]\n"
            else:
                order_status_context += "All required information has been provided. Order will be completed automatically.\n"
            if order_data.get('special_request') and order_data['special_request'] != 'None':
                order_status_context += f"Special request: {order_data['special_request']}\n"

        # Build the conversation history prompt
        history_prompt = ""
        for msg in history:
            if msg.get("sender") == "user":
                history_prompt += f"User: {msg['text']}\n"
            elif msg.get("sender") == "bot":
                history_prompt += f"Assistant: {msg['text']}\n"

        # Prepare the payload for Ollama
        prompt = system_prompt
        
        # Place order_status_context at the very top of the prompt
        if order_status_context:
            prompt = f"{order_status_context}\n\n" + prompt
        if menu_context:
            prompt += f"\n\n{menu_context}"
        if menu_items_context:
            prompt += f"\n\n{menu_items_context}"
        if order_context:
            prompt += f"\n\n{order_context}"
        if open_restaurants_context:
            prompt += f"\n\n{open_restaurants_context}"
        prompt += f"\n{history_prompt}User: {user_message}\nAssistant:"

        # Log the full prompt for debugging
        print("\n================ DEBUG: LLM PROMPT ================")
        print(prompt)
        print("================ END DEBUG: LLM PROMPT ================\n")
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.1
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
            "stream": False,
            "temperature": 0.1
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

@app.post('/debug/test_order_changes/{session_id}')
def test_order_changes(session_id: str):
    """Debug endpoint to test order change detection"""
    
    # Clear existing conversation
    ConversationLogger.cleanup_session(session_id)
    
    # Simulate conversation with order changes
    test_conversation = [
        ("user", "hi, do you have burgers?"),
        ("bot", "Yes, we have burgers for AED 25 each"),
        ("user", "I want 5 burgers"),
        ("bot", "Great! 5 burgers for AED 125. Please provide your NYU ID"),
        ("user", "actually, I want 3 burgers instead"),
        ("user", "my nyu id is 12345678"),
        ("user", "building A1A"),
        ("user", "phone 971501234567"),
        ("user", "no special requests")
    ]
    
    # Log all messages
    for sender, message in test_conversation:
        ConversationLogger.log_message(session_id, message, sender)
    
    # Extract final order data
    conversation = ConversationLogger.get_conversation(session_id)
    order_data = extract_order_completion_data(conversation)
    
    # Get the quantity of burgers in final order
    burger_quantity = None
    if order_data and order_data['items']:
        for item in order_data['items']:
            if 'burger' in item['name'].lower():
                burger_quantity = item['quantity']
                break
    
    return {
        "test": "order_change_detection",
        "conversation_length": len(conversation),
        "final_order_data": order_data,
        "burger_quantity_final": burger_quantity,
        "should_be_3": burger_quantity == 3,
        "test_passed": burger_quantity == 3,
        "session_id": session_id
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