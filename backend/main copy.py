import os
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import json
import re
import datetime
import phonenumbers
from typing import Dict, Optional, List, Union

MENU_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'menu.json'))

# Import our background order system
from background_order_system import (
    ConversationLogger, OrderKeywordDetector, BackgroundOrderProcessor
)
from menu_embeddings import rag_extract_menu_items, rag_extract_menu_item, format_items_summary
from menu_embeddings import is_category_name

# Define the path to the system prompt file
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt.txt')

# Ollama API endpoint (assumes Ollama is running locally)
OLLAMA_URL = 'http://localhost:11434/api/generate'
# OLLAMA_MODEL = 'qwen2.5'
OLLAMA_MODEL = 'mistral'

# MCP server endpoints
MCP_ITEM_URL = 'http://localhost:9000/menu/item'
MCP_MENU_URL = 'http://localhost:9000/menu/today'
MCP_CATEGORY_URL = 'http://localhost:9000/menu/category'

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

# Validation Functions
def validate_nyu_id(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid NYU ID (8 digits)"""
    if not text:
        return {"valid": False, "message": "No NYU ID found", "nyu_id": None}
    
    # Find any 8-digit number in the text
    nyu_id_match = re.search(r'\b(\d{8})\b', text)
    if not nyu_id_match:
        return {"valid": False, "message": "NYU ID must be exactly 8 digits", "nyu_id": None}
    
    nyu_id = nyu_id_match.group(1)
    return {"valid": True, "message": "Valid NYU ID", "nyu_id": nyu_id}

def validate_phone_number(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid UAE phone number"""
    if not text:
        return {"valid": False, "message": "No phone number found", "phone": None}
    
    # Clean the text of spaces and hyphens
    cleaned_text = text.replace(' ', '').replace('-', '')
    
    # Find any number between 9-15 digits
    phone_match = re.search(r'\b(\d{9,15})\b', cleaned_text)
    if not phone_match:
        return {"valid": False, "message": "Phone number must be between 9 and 15 digits", "phone": None}
    
    phone = phone_match.group(1)
    try:
        # Validate as UAE number
        parsed = phonenumbers.parse(phone, "AE")
        if phonenumbers.is_valid_number(parsed):
            national_number = str(parsed.national_number)
            if len(national_number) >= 9 and len(national_number) <= 15 and national_number.startswith('5'):
                return {"valid": True, "message": "Valid phone number", "phone": phone}
    except Exception:
        pass
    
    return {"valid": False, "message": "Invalid UAE mobile number format", "phone": None}

def validate_building(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid building number"""
    if not text:
        return {"valid": False, "message": "No building number found", "building": None}
    
    # Find building number pattern (A1A, A2B, etc.)
    building_match = re.search(r'\b(A\d[ABC])\b', text, re.IGNORECASE)
    if not building_match:
        return {"valid": False, "message": f"Building must be one of: {', '.join(AVAILABLE_BUILDINGS)}", "building": None}
    
    building = building_match.group(1).upper()
    if building not in AVAILABLE_BUILDINGS:
        return {"valid": False, "message": f"Invalid building. Must be one of: {', '.join(AVAILABLE_BUILDINGS)}", "building": None}
    
    return {"valid": True, "message": "Valid building", "building": building}

# Tool definitions for Mistral
VALIDATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "validate_nyu_id",
            "description": "Validate if the text contains a valid NYU ID (must be exactly 8 digits)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract and validate NYU ID from",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_phone_number",
            "description": "Validate if the text contains a valid UAE phone number (must be between 9-15 digits and start with 5)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract and validate phone number from",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_building",
            "description": f"Validate if the text contains a valid building number (must be one of: {', '.join(AVAILABLE_BUILDINGS)})",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract and validate building number from",
                    }
                },
                "required": ["text"],
            },
        },
    }
]

# Function mapping for execution
VALIDATION_FUNCTIONS = {
    'validate_nyu_id': validate_nyu_id,
    'validate_phone_number': validate_phone_number,
    'validate_building': validate_building
}

# Add normalization function

def normalize_order_items(items):
    """
    Given a list of items, return only valid item dicts with 'name', 'price', 'quantity', 'total_price'.
    Log and skip any invalid or category items.
    """
    valid_items = []
    for item in items or []:
        if not isinstance(item, dict):
            print(f"[normalize_order_items] Skipping non-dict item: {item}")
            continue
        if 'name' in item and 'price' in item:
            # Ensure quantity and total_price
            qty = item.get('quantity', 1)
            price = item['price']
            total_price = item.get('total_price', price * qty)
            valid_items.append({
                'name': item['name'],
                'price': price,
                'quantity': qty,
                'total_price': total_price
            })
        else:
            print(f"[normalize_order_items] Skipping invalid or category item: {item}")
    return valid_items

# Refactor OrderState to always use normalization
class OrderState:
    def __init__(self):
        self.in_order_flow = False
        self.nyu_id = None
        self.building = None
        self.phone = None
        self.items = None
        self.total_cost = 0.0
        self.special_request = None

    def start_order(self, items, total_cost):
        self.in_order_flow = True
        self.items = normalize_order_items(items)
        self.total_cost = total_cost
        self.special_request = None  # Reset special request when starting new order

    def reset(self):
        self.__init__()

    def to_dict(self):
        return {
            "in_order_flow": self.in_order_flow,
            "nyu_id": self.nyu_id,
            "building": self.building,
            "phone": self.phone,
            "items": self.items,
            "total_cost": self.total_cost,
            "special_request": self.special_request
        }

# Global order state storage
order_states: Dict[str, OrderState] = {}

def get_or_create_order_state(session_id: str) -> OrderState:
    if session_id not in order_states:
        order_states[session_id] = OrderState()
    return order_states[session_id]

def extract_order_completion_data(conversation: List[Dict]) -> Optional[Dict]:
    """Extract order completion data from conversation history"""
    
    user_messages = []
    bot_messages = []
    
    for msg in conversation:
        if msg['sender'] == 'user':
            user_messages.append(msg['message'])
        else:
            bot_messages.append(msg['message'])
    
    # Combine all user messages for analysis
    combined_text = " ".join(user_messages)
    
    # Extract order information
    items = rag_extract_menu_items(combined_text)
    items = normalize_order_items(items)
    
    # Extract NYU ID (8 digits) - must be explicitly provided
    nyu_id_match = re.search(r'\b(\d{8})\b', combined_text)
    nyu_id = nyu_id_match.group(1) if nyu_id_match else None
    nyu_id_valid = validate_nyu_id(nyu_id) if nyu_id else False
    
    # Extract building (A1A, A2B, etc.) - must be explicitly provided
    building_match = re.search(r'\b(A\d[ABC])\b', combined_text, re.IGNORECASE)
    building = building_match.group(1).upper() if building_match else None
    building_valid = validate_building(building) if building else False
    
    # Extract phone (UAE mobile number validation)
    phone_match = re.search(r'\b(\d{9,15})\b', combined_text.replace(' ', '').replace('-', ''))
    phone = phone_match.group(1) if phone_match else None
    
    # Validate phone number (UAE mobile: +9715xxxxxxxx)
    valid_phone = False
    if phone:
        try:
            parsed = phonenumbers.parse(phone, "AE")
            if phonenumbers.is_valid_number(parsed) and phonenumbers.region_code_for_number(parsed) == "AE":
                # Get the national number (should be 9-15 digits, start with 5)
                national_number = str(parsed.national_number)
                if len(national_number) >= 9 and len(national_number) <= 15 and national_number.startswith('5'):
                    valid_phone = True
        except Exception:
            valid_phone = False
    
    # Extract special requests
    special_request = "None"
    for msg in reversed(user_messages[-10:]):
        if any(keyword in msg.lower() for keyword in ['special', 'request', 'note', 'dietary', 'allergy']):
            if not any(word in msg.lower() for word in ['no', 'none', 'nothing']):
                special_request = msg
                break
    
    # Check if we have all required fields and they're valid
    has_all_fields = (items and nyu_id_valid and building_valid and valid_phone)
    
    if items:
        order_data = {
            'items': items,
            'total_cost': sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items),
            'nyu_id': nyu_id,
            'building': building,
            'phone': phone,
            'special_request': special_request,
            'is_complete': has_all_fields,
            'nyu_id_valid': nyu_id_valid,
            'building_valid': building_valid,
            'valid_phone': valid_phone
        }
        
        # Track both missing and invalid fields
        missing_fields = []
        invalid_fields = []
        
        if not nyu_id:
            missing_fields.append('nyu_id')
        elif not nyu_id_valid:
            invalid_fields.append('nyu_id')
            
        if not building:
            missing_fields.append('building')
        elif not building_valid:
            invalid_fields.append('building')
            
        if not phone:
            missing_fields.append('phone')
        elif not valid_phone:
            invalid_fields.append('phone')
        
        order_data['missing_fields'] = missing_fields
        order_data['invalid_fields'] = invalid_fields
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
    
    # Only handle order confirmation and cancellation
    if stage == "confirming_order":
        if re.search(r'\b(yes|yeah|yep|confirm|ok|okay|sure|correct|right|proceed)\b', user_message_lower):
            # Start the order flow
            order_state = get_or_create_order_state(session_id)
            order_state.start_order(items, total_cost)
            return None  # Let the LLM handle the response with function calling
        elif re.search(r'\b(no|nah|nope|cancel|wrong|incorrect)\b', user_message_lower):
            OrderKeywordDetector.save_detected_order(session_id, None)
            # Reset order state
            order_state = get_or_create_order_state(session_id)
            order_state.reset()
            return None  # Let the LLM handle the response
    
    return None

async def ollama_stream():
    # Check if the user is asking for the full menu
    if re.search(r"what'?s on the menu|show me the menu|today'?s menu|full menu", user_message, re.IGNORECASE):
        yield "[Fetching menu data...]\n"
    
    # RAG-based multiple item extraction for immediate responses
    items_data = rag_extract_menu_items(user_message)
    # Normalize acai bowl orders
    new_items_data = []
    for item in items_data:
        if 'text' in item and ('acai' in item['text'].lower() or 'bowl' in item['text'].lower()):
            acai_item = parse_acai_bowl_order(item['text'])
            if acai_item:
                new_items_data.append(acai_item)
            else:
                new_items_data.append(item)
        else:
            new_items_data.append(item)
    items_data = new_items_data
    menu_items_context = ""
    order_context = ""
    category_context = ""

    if items_data:
        found_items = []
        not_found_items = []
        found_categories = []
        for item_data in items_data:
            if 'category' in item_data:
                category_name = item_data['category']
                yield f"[Looking up item/category '{category_name}' in the menu...]\n"
                category_items = await fetch_menu_category_from_mcp(category_name)
                if category_items:
                    found_categories.append({'category': category_name, 'items': category_items})
                else:
                    not_found_items.append(category_name)
            elif 'name' in item_data:
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
        if found_categories:
            for cat in found_categories:
                cat_name = cat['category']
                cat_items = cat['items']
                # Special-case for Acai Bowls
                if cat_name.lower() == 'acai bowls':
                    # Load the menu.json to get full structure
                    with open(MENU_PATH, 'r') as f:
                        menu_data = json.load(f)
                    acai = menu_data.get('Acai Bowls', {})
                    # Extract sizes and prices
                    sizes = [(k, v) for k, v in acai.items() if k in ['Small', 'Large']]
                    # Extract flavors and descriptions
                    flavors = [(k, v) for k, v in acai.items() if k not in ['Small', 'Large']]
                    acai_context = "[ACAI BOWLS]\nSizes:\n"
                    for size, price in sizes:
                        acai_context += f"- {size}: AED {price}\n"
                    acai_context += "\nFlavors:\n"
                    for flavor, desc in flavors:
                        acai_context += f"- {flavor}: {desc}\n"
                    acai_context += ("\nPlease select a flavor and a size for your acai bowl order. "
                                     "For example: 'Small OG Bowl' or 'Large Choco Bowl'.")
                    category_context += f"\n{acai_context}\n"
                else:
                    if cat_items:
                        cat_summary = "\n".join([f"- {i['name']}: AED {i['price']}" for i in cat_items])
                        category_context += f"\n[MENU CATEGORY: {cat_name}]\n{cat_summary}\n"
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
        invalid_fields = order_data.get('invalid_fields', [])
        
        order_status_context = "\n[[ORDER STATUS]]\n"
        if order_data['items']:
            items_text = ", ".join([f"{item.get('quantity', 1)}x {item['name']}" for item in order_data['items']])
            order_status_context += f"Current order: {items_text} (Total: AED {order_data['total_cost']:.2f})\n"
        
        # Add validation context
        order_status_context += "\n[[VALIDATION REQUIREMENTS]]\n"
        order_status_context += "- NYU ID must be exactly 8 digits\n"
        order_status_context += f"- Building must be one of: {', '.join(AVAILABLE_BUILDINGS)}\n"
        order_status_context += "- Phone number must be a valid UAE mobile number starting with '5'\n"
        
        if missing_fields or invalid_fields:
            order_status_context += "\n[[VALIDATION STATUS]]\n"
            
            if missing_fields:
                order_status_context += "Missing information:\n"
                for field in missing_fields:
                    order_status_context += f"- {field}\n"
            
            if invalid_fields:
                order_status_context += "Invalid information provided:\n"
                for field in invalid_fields:
                    if field == 'nyu_id':
                        order_status_context += f"- NYU ID '{order_data['nyu_id']}' is invalid (must be 8 digits)\n"
                    elif field == 'building':
                        order_status_context += f"- Building '{order_data['building']}' is not a valid option\n"
                    elif field == 'phone':
                        order_status_context += f"- Phone number '{order_data['phone']}' is not a valid UAE mobile number\n"
        else:
            order_status_context += "\nAll required information has been provided and validated.\n"
        
        if order_data.get('special_request') and order_data['special_request'] != 'None':
            order_status_context += f"\nSpecial request: {order_data['special_request']}\n"

    # Build the conversation history prompt
    history_prompt = "[CHAT HISTORY] (for your reference only)"
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
        prompt += f"\n\n{menu_items_context}"
    if category_context:
        prompt += f"\n\n{category_context}"
    if order_context:
        prompt += f"\n\n{order_context}"
    if order_status_context:
        prompt += f"\n\n{order_status_context}"
    if open_restaurants_context:
        prompt += f"\n\n{open_restaurants_context}"
    prompt += f"\n{history_prompt}User: {user_message}\nAssistant:"

    # Add order state context if in order flow
    order_state = get_or_create_order_state(session_id)
    
    if order_state.in_order_flow:
        order_status = "\n[[ORDER STATUS]]\n"
        items_inner = ', '.join([
            f"{item.get('quantity', 1)}x {item['name']}"
            for item in (order_state.items or [])
            if isinstance(item, dict) and 'name' in item
        ])
        order_status += f"Items: {items_inner}\n"
        order_status += f"Total: AED {order_state.total_cost:.2f}\n"
        
        # Show provided information
        order_status += "\nProvided Information:\n"
        if order_state.nyu_id:
            order_status += f"- NYU ID: {order_state.nyu_id}\n"
        if order_state.building:
            order_status += f"- Building: {order_state.building}\n"
        if order_state.phone:
            order_status += f"- Phone: {order_state.phone}\n"
        if order_state.special_request is not None:
            order_status += f"- Special Request: {order_state.special_request}\n"
        
        # Show missing information
        order_status += "\nMissing Information:\n"
        if not order_state.nyu_id:
            order_status += "- NYU ID (must be 8 digits)\n"
        if not order_state.building:
            order_status += f"- Building (must be one of: {', '.join(AVAILABLE_BUILDINGS)})\n"
        if not order_state.phone:
            order_status += "- Phone number (must be a valid UAE mobile number)\n"
        if order_state.special_request is None:
            order_status += "- Special Request (ask if they have any special requests, dietary restrictions, etc.)\n"
        
        prompt += order_status
        
        # Add validation tools to the payload
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
            "tools": VALIDATION_TOOLS
        }
    else:
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
                        elif "tool_calls" in data:
                            # Handle tool calls
                            for tool_call in data["tool_calls"]:
                                function_name = tool_call["function"]["name"]
                                function_args = json.loads(tool_call["function"]["arguments"])
                                
                                if function_name in VALIDATION_FUNCTIONS:
                                    result = VALIDATION_FUNCTIONS[function_name](**function_args)
                                    
                                    # Update order state based on validation results
                                    if result["valid"]:
                                        if function_name == "validate_nyu_id":
                                            order_state.nyu_id = result["nyu_id"]
                                        elif function_name == "validate_phone_number":
                                            order_state.phone = result["phone"]
                                        elif function_name == "validate_building":
                                            order_state.building = result["building"]
                                    
                                    # Add validation result to prompt context
                                    prompt += f"\n[[VALIDATION RESULT]]\n{json.dumps(result)}\n"
                                    
                                    # Get model's response to the validation
                                    validation_response = await client.post(
                                        OLLAMA_URL,
                                        json={"model": OLLAMA_MODEL, "prompt": prompt}
                                    )
                                    validation_data = validation_response.json()
                                    if "response" in validation_data:
                                        chunk = validation_data["response"]
                                        bot_response += chunk
                                        yield chunk
                    except Exception as e:
                        print(f"Streaming parse error: {e}")
        except httpx.RequestError as e:
            print(f"Ollama connection error: {e}")
            yield "[Sorry, there was an error connecting to the AI server. Please try again later or contact support.]"
        except Exception as e:
            print(f"Ollama streaming error: {e}")
            error_msg = "[Sorry, an unexpected error occurred while processing your request. Please try again later.]"
            bot_response = error_msg
            yield error_msg
    
    # Log the bot response after streaming is complete
    if bot_response:
        ConversationLogger.log_message(session_id, bot_response, "bot")

def check_for_order_completion(session_id: str) -> Optional[str]:
    """Check if an order can be completed"""
    order_state = get_or_create_order_state(session_id)
    
    if not order_state.in_order_flow:
        return None
    
    # Check if all required information is valid
    if (order_state.nyu_id and 
        order_state.building and order_state.building in AVAILABLE_BUILDINGS and
        order_state.phone and
        order_state.special_request is not None):  # Include special request check
        
        # Format order data for saving
        order_data = {
            'items': order_state.items,
            'total_cost': order_state.total_cost,
            'nyu_id': order_state.nyu_id,
            'building': order_state.building,
            'phone': order_state.phone,
            'special_request': order_state.special_request
        }
        
        # Save the completed order
        save_final_order_to_file(order_data)
        
        # Clean up
        ConversationLogger.cleanup_session(session_id)
        order_state.reset()
        
        # Return confirmation message
        return ("Your order is confirmed! Please take your receipt to the dining hall to pick up your food. "
                "Thank you for ordering with us!")
    
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

async def fetch_menu_category_from_mcp(category_name: str):
    """Query the MCP server for all items in a category by name."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(MCP_CATEGORY_URL, params={"category": category_name}, timeout=2)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
    except Exception as e:
        print(f"Error fetching menu category from MCP: {e}")
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

def parse_acai_bowl_order(text: str) -> Optional[Dict]:
    """
    Parse an acai bowl order from text like 'Small OG Bowl', return item dict with name, price, quantity, total_price.
    """
    try:
        with open(MENU_PATH, 'r') as f:
            menu = json.load(f)
        acai = menu.get('Acai Bowls', {})
        sizes = {k.lower(): v for k, v in acai.items() if k in ['Small', 'Large']}
        flavors = [k.lower() for k in acai.keys() if k not in ['Small', 'Large']]
        # Look for size and flavor in text
        size_match = None
        for size in sizes:
            if re.search(rf'\b{size}\b', text.lower()):
                size_match = size
                break
        flavor_match = None
        for flavor in flavors:
            if flavor in text.lower():
                flavor_match = flavor
                break
        if size_match and flavor_match:
            price = sizes[size_match]
            name = f"{size_match.capitalize()} {flavor_match.title()} Bowl"
            return {
                'name': name,
                'price': price,
                'quantity': 1,
                'total_price': price * 1
            }
    except Exception as e:
        print(f"Error parsing acai bowl order: {e}")
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
    
    # Get order state
    order_state = get_or_create_order_state(session_id)
    
    # Check for special request responses
    if order_state.in_order_flow and order_state.special_request is None:
        user_message_lower = user_message.lower().strip()
        if user_message_lower in ['no', 'none', 'n/a', 'no special requests', 'nothing']:
            order_state.special_request = 'None'
        elif not re.search(r'\b(nyu|id|building|phone|number)\b', user_message_lower):
            # If message doesn't look like other order info, treat as special request
            order_state.special_request = user_message.strip()
    
    # Check for explicit order cancellation
    direct_response = check_for_direct_order_response(session_id, user_message)
    if direct_response:
        async def direct_response_stream():
            yield direct_response
        
        ConversationLogger.log_message(session_id, direct_response, "bot")
        return StreamingResponse(direct_response_stream(), media_type="text/plain")
    
    # Extract current order state
    order_data = extract_order_completion_data(ConversationLogger.get_conversation(session_id))
    # If waiting for special request
    if hasattr(order_state, 'special_request') and order_state.special_request is None:
        user_message_lower = body["message"].strip().lower()
        if user_message_lower in ['no', 'none', 'n/a', 'no special requests']:
            order_state.special_request = 'None'
        else:
            order_state.special_request = body["message"].strip()
        # After setting, check for order completion again
        completion_message = check_for_order_completion(session_id)
        if completion_message:
            async def completion_response_stream():
                yield completion_message
            ConversationLogger.log_message(session_id, completion_message, "bot")
            return StreamingResponse(completion_response_stream(), media_type="text/plain")

    # Check for order completion
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
        # Normalize acai bowl orders
        new_items_data = []
        for item in items_data:
            if 'text' in item and ('acai' in item['text'].lower() or 'bowl' in item['text'].lower()):
                acai_item = parse_acai_bowl_order(item['text'])
                if acai_item:
                    new_items_data.append(acai_item)
                else:
                    new_items_data.append(item)
            else:
                new_items_data.append(item)
        items_data = new_items_data
        menu_items_context = ""
        order_context = ""
        category_context = ""

        if items_data:
            found_items = []
            not_found_items = []
            found_categories = []
            for item_data in items_data:
                if 'category' in item_data:
                    category_name = item_data['category']
                    yield f"[Looking up category '{category_name}' in the menu...]\n"
                    category_items = await fetch_menu_category_from_mcp(category_name)
                    if category_items:
                        found_categories.append({'category': category_name, 'items': category_items})
                    else:
                        not_found_items.append(category_name)
                elif 'name' in item_data:
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
            if found_categories:
                for cat in found_categories:
                    cat_name = cat['category']
                    cat_items = cat['items']
                    # Special-case for Acai Bowls
                    if cat_name.lower() == 'acai bowls':
                        # Load the menu.json to get full structure
                        with open(MENU_PATH, 'r') as f:
                            menu_data = json.load(f)
                        acai = menu_data.get('Acai Bowls', {})
                        # Extract sizes and prices
                        sizes = [(k, v) for k, v in acai.items() if k in ['Small', 'Large']]
                        # Extract flavors and descriptions
                        flavors = [(k, v) for k, v in acai.items() if k not in ['Small', 'Large']]
                        acai_context = "[ACAI BOWLS]\nSizes:\n"
                        for size, price in sizes:
                            acai_context += f"- {size}: AED {price}\n"
                        acai_context += "\nFlavors:\n"
                        for flavor, desc in flavors:
                            acai_context += f"- {flavor}: {desc}\n"
                        acai_context += ("\nPlease select a flavor and a size for your acai bowl order. "
                                         "For example: 'Small OG Bowl' or 'Large Choco Bowl'.")
                        category_context += f"\n{acai_context}\n"
                    else:
                        if cat_items:
                            cat_summary = "\n".join([f"- {i['name']}: AED {i['price']}" for i in cat_items])
                            category_context += f"\n[MENU CATEGORY: {cat_name}]\n{cat_summary}\n"
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
            invalid_fields = order_data.get('invalid_fields', [])
            
            order_status_context = "\n[[ORDER STATUS]]\n"
            if order_data['items']:
                items_text = ", ".join([
                    f"{item.get('quantity', 1)}x {item['name']}"
                    for item in order_data['items']
                    if isinstance(item, dict) and 'name' in item
                ])
                if items_text:
                    order_status_context += f"Current order: {items_text} (Total: AED {order_data['total_cost']:.2f})\n"
                else:
                    order_status_context += f"Current order: [No individual items listed] (Total: AED {order_data['total_cost']:.2f})\n"
            
            # Add validation context
            order_status_context += "\n[[VALIDATION REQUIREMENTS]]\n"
            order_status_context += "- NYU ID must be exactly 8 digits\n"
            order_status_context += f"- Building must be one of: {', '.join(AVAILABLE_BUILDINGS)}\n"
            order_status_context += "- Phone number must be a valid UAE mobile number starting with '5'\n"
            
            if missing_fields or invalid_fields:
                order_status_context += "\n[[VALIDATION STATUS]]\n"
                
                if missing_fields:
                    order_status_context += "Missing information:\n"
                    for field in missing_fields:
                        order_status_context += f"- {field}\n"
                
                if invalid_fields:
                    order_status_context += "Invalid information provided:\n"
                    for field in invalid_fields:
                        if field == 'nyu_id':
                            order_status_context += f"- NYU ID '{order_data['nyu_id']}' is invalid (must be 8 digits)\n"
                        elif field == 'building':
                            order_status_context += f"- Building '{order_data['building']}' is not a valid option\n"
                        elif field == 'phone':
                            order_status_context += f"- Phone number '{order_data['phone']}' is not a valid UAE mobile number\n"
            else:
                order_status_context += "\nAll required information has been provided and validated.\n"
            
            if order_data.get('special_request') and order_data['special_request'] != 'None':
                order_status_context += f"\nSpecial request: {order_data['special_request']}\n"

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
            prompt += f"\n\n{menu_items_context}"
        if category_context:
            prompt += f"\n\n{category_context}"
        if order_context:
            prompt += f"\n\n{order_context}"
        if order_status_context:
            prompt += f"\n\n{order_status_context}"
        if open_restaurants_context:
            prompt += f"\n\n{open_restaurants_context}"
        prompt += f"\n{history_prompt}User: {user_message}\nAssistant:"

        # Add order state context if in order flow
        order_state = get_or_create_order_state(session_id)
        
        if order_state.in_order_flow:
            order_status = "\n[[ORDER STATUS]]\n"
            items_inner = ', '.join([
                f"{item.get('quantity', 1)}x {item['name']}"
                for item in (order_state.items or [])
                if isinstance(item, dict) and 'name' in item
            ])
            order_status += f"Items: {items_inner}\n"
            order_status += f"Total: AED {order_state.total_cost:.2f}\n"
            
            # Show provided information
            order_status += "\nProvided Information:\n"
            if order_state.nyu_id:
                order_status += f"- NYU ID: {order_state.nyu_id}\n"
            if order_state.building:
                order_status += f"- Building: {order_state.building}\n"
            if order_state.phone:
                order_status += f"- Phone: {order_state.phone}\n"
            if order_state.special_request is not None:
                order_status += f"- Special Request: {order_state.special_request}\n"
            
            # Show missing information
            order_status += "\nMissing Information:\n"
            if not order_state.nyu_id:
                order_status += "- NYU ID (must be 8 digits)\n"
            if not order_state.building:
                order_status += f"- Building (must be one of: {', '.join(AVAILABLE_BUILDINGS)})\n"
            if not order_state.phone:
                order_status += "- Phone number (must be a valid UAE mobile number)\n"
            if order_state.special_request is None:
                order_status += "- Special Request (ask if they have any special requests, dietary restrictions, etc.)\n"
            
            prompt += order_status
            
            # Add validation tools to the payload
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "tools": VALIDATION_TOOLS
            }
        else:
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
                            elif "tool_calls" in data:
                                # Handle tool calls
                                for tool_call in data["tool_calls"]:
                                    function_name = tool_call["function"]["name"]
                                    function_args = json.loads(tool_call["function"]["arguments"])
                                    
                                    if function_name in VALIDATION_FUNCTIONS:
                                        result = VALIDATION_FUNCTIONS[function_name](**function_args)
                                        
                                        # Update order state based on validation results
                                        if result["valid"]:
                                            if function_name == "validate_nyu_id":
                                                order_state.nyu_id = result["nyu_id"]
                                            elif function_name == "validate_phone_number":
                                                order_state.phone = result["phone"]
                                            elif function_name == "validate_building":
                                                order_state.building = result["building"]
                                        
                                        # Add validation result to prompt context
                                        prompt += f"\n[[VALIDATION RESULT]]\n{json.dumps(result)}\n"
                                        
                                        # Get model's response to the validation
                                        validation_response = await client.post(
                                            OLLAMA_URL,
                                            json={"model": OLLAMA_MODEL, "prompt": prompt}
                                        )
                                        validation_data = validation_response.json()
                                        if "response" in validation_data:
                                            chunk = validation_data["response"]
                                            bot_response += chunk
                                            yield chunk
                        except Exception as e:
                            print(f"Streaming parse error: {e}")
            except httpx.RequestError as e:
                print(f"Ollama connection error: {e}")
                yield "[Sorry, there was an error connecting to the AI server. Please try again later or contact support.]"
            except Exception as e:
                print(f"Ollama streaming error: {e}")
                error_msg = "[Sorry, an unexpected error occurred while processing your request. Please try again later.]"
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