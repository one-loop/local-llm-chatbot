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
OLLAMA_MODEL = 'qwen2.5'

# MCP server endpoints
MCP_ITEM_URL = 'http://localhost:9000/menu/item'
MCP_MENU_URL = 'http://localhost:9000/menu/today'
MCP_CATEGORY_URL = 'http://localhost:9000/menu/category'

RESTAURANTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'restaurants.json'))

# Final order storage path
ORDERS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'orders.txt'))

# Available buildings
AVAILABLE_BUILDINGS = ["A1A", "A1B", "A1C", "A2A", "A2B", "A2C", "A3", "A4", "A5A", "A5B", "A5C", "A6A", "A6B", "A6C", "A1", "A2", "A5", "A6", "F1", "F2", "C1", "C2", "C3"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add this debug function at the top after your imports
def debug_log(message: str):
    """Enhanced debug logging"""
    print(f"[DEBUG {datetime.datetime.now().strftime('%H:%M:%S')}] {message}")

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

def save_final_order_to_file(order_data: Dict):
    """Save completed order to final orders file"""
    try:
        # Use 'a' mode to append orders to the file
        with open(ORDERS_PATH, '', encoding='utf-8') as f:
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
            
            f.write(f"RF ID: N{order_data.get('rf_id', 'N/A')}\n")
            f.write(f"Building: {order_data.get('building', 'N/A')}\n")
            f.write(f"Phone: {order_data.get('phone', 'N/A')}\n")
            f.write(f"Special Request: {order_data.get('special_request', 'None')}\n")
            f.write("=" * 50 + "\n")
            
        print(f"DEBUG: Saved final order to file")
        
    except Exception as e:
        print(f"Error saving order: {e}")

# Individual Validation Functions (kept for tool system)
def validate_rf_id(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid RF ID (6 digits)"""
    if not text:
        return {"valid": False, "message": "No RF ID found", "rf_id": None}
    
    # Find any 6-digit number in the text
    rf_id_match = re.search(r'\b(\d{6})\b', text)
    if not rf_id_match:
        return {"valid": False, "message": "RF ID must be exactly 6 digits", "rf_id": None}
    
    rf_id = rf_id_match.group(1)
    return {"valid": True, "message": "Valid RF ID", "rf_id": rf_id}

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
    
    # Find building number pattern (A1A, A2B, F1, C2, etc.)
    building_match = re.search(r'\b(A\d[ABC]|[AFC]\d)\b', text, re.IGNORECASE)
    if not building_match:
        return {"valid": False, "message": f"Building must be one of: {', '.join(sorted(AVAILABLE_BUILDINGS))}", "building": None}
    
    building = building_match.group(1).upper()
    if building not in AVAILABLE_BUILDINGS:
        return {"valid": False, "message": f"Invalid building. Must be one of: {', '.join(sorted(AVAILABLE_BUILDINGS))}", "building": None}
    
    return {"valid": True, "message": "Valid building", "building": building}

# CONSOLIDATED VALIDATION FUNCTION
def validate_and_update_order_state(user_message: str, order_state) -> Optional[str]:
    """
    Consolidated validation function that extracts and validates user input formats BEFORE sending to LLM.
    Updates order_state with valid data.
    Returns error message if validation fails, None if valid or no validation needed.
    """
    user_message_lower = user_message.lower()
    debug_log(f"Validating input: '{user_message}'")
    
    # Extract potential RFID (6 digits)
    rf_id_match = re.search(r'\b(\d{4,7})\b', user_message)
    if rf_id_match:
        potential_rfid = rf_id_match.group(1)
        if len(potential_rfid) != 6:
            if len(potential_rfid) < 6:
                return f"Your RFID must be exactly 6 digits. You provided {len(potential_rfid)} digits ({potential_rfid}). Please provide your complete 6-digit RFID."
            else:
                return f"Your RFID must be exactly 6 digits. You provided {len(potential_rfid)} digits ({potential_rfid}). Please check your RFID and provide exactly 6 digits."
        
        # If we reach here, RFID is valid - update order state
        order_state.rf_id = potential_rfid
        debug_log(f"Updated RFID to {potential_rfid}")
    
    # Extract potential building number - FIXED REGEX
    building_match = re.search(r'\b([A-Z]\d[A-Z]?)\b', user_message, re.IGNORECASE)
    if building_match:
        potential_building = building_match.group(1).upper()
        debug_log(f"Found potential building: {potential_building}")
        
        # Check against available buildings
        if potential_building not in AVAILABLE_BUILDINGS:
            debug_log(f"Building {potential_building} is INVALID")
            return f"'{potential_building}' is not a valid building. Please choose from: {', '.join(sorted(AVAILABLE_BUILDINGS))}"
        
        # If we reach here, building is valid - update order state
        order_state.building = potential_building
        debug_log(f"Updated building to {potential_building}")
    
    # Extract potential phone number (look for UAE mobile patterns)
    phone_match = re.search(r'\b(05\d{8}|\d{10})\b', user_message.replace(' ', '').replace('-', ''))
    if phone_match:
        potential_phone = phone_match.group(1)
        
        # Clean the phone number
        cleaned_phone = potential_phone.replace('+971', '').replace(' ', '').replace('-', '')
        
        # UAE mobile validation
        if not cleaned_phone.startswith('05') or len(cleaned_phone) != 10:
            if cleaned_phone.startswith('5') and len(cleaned_phone) == 9:
                cleaned_phone = '0' + cleaned_phone
            else:
                return f"Please provide a valid UAE mobile number. UAE mobile numbers start with '05' and have 10 digits total (format: 05xxxxxxxx)."
        
        # If we reach here, phone is valid - update order state
        order_state.phone = cleaned_phone
        debug_log(f"Updated phone to {cleaned_phone}")
    
    # No validation errors found
    return None

# Tool definitions for Mistral
VALIDATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "validate_rf_id",
            "description": "Validate if the text contains a valid RF ID (must be exactly 6 digits)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract and validate RF ID from",
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
            "description": f"Validate if the text contains a valid building number (must be one of: {', '.join(sorted(AVAILABLE_BUILDINGS))})",
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
    'validate_rf_id': validate_rf_id,
    'validate_phone_number': validate_phone_number,
    'validate_building': validate_building
}
async def analyze_conversation_with_llm(conversation: List[Dict], session_id: str) -> Optional[Dict]:
    """
    Use LLM to analyze conversation and extract order details
    Returns order data if found, None otherwise
    """
    debug_log("Using LLM to analyze conversation for order details")
    
    # Build conversation text
    conversation_text = ""
    for msg in conversation[-10:]:  # Last 10 messages for context
        sender = msg['sender']
        message = msg['message']
        conversation_text += f"{sender.title()}: {message}\n"
    
    # Create analysis prompt
    analysis_prompt = f"""Analyze this conversation between a user and a food ordering assistant. Extract order details if an order is being placed.

CONVERSATION:
{conversation_text}

TASK: Determine if there is a complete food order in this conversation and extract the details.

Look for:
1. ITEMS: What food items are being ordered (name, quantity, price)
2. CUSTOMER INFO: RFID (6 digits), Building (A1A, A2B, F1, etc.), Phone (UAE mobile)
3. ORDER STATUS: Is this a confirmed/completed order ready to be processed?

IMPORTANT RULES:
- Only extract if this looks like a CONFIRMED/COMPLETED order
- RFID must be exactly 6 digits
- Building must match format: A1A, A1B, A1C, A2A, A2B, A2C, A3, A4, A5A, A5B, A5C, A6A, A6B, A6C, A1, A2, A5, A6, F1, F2, C1, C2, C3
- Phone must be UAE mobile number (10 digits starting with 05)
- Look for order summaries, totals, confirmations

RESPOND ONLY IN THIS JSON FORMAT:
{{
    "has_order": true/false,
    "order_confirmed": true/false,
    "items": [
        {{
            "name": "item name",
            "price": price_number,
            "quantity": quantity_number,
            "total_price": total_price_number
        }}
    ],
    "customer_info": {{
        "rfid": "6_digit_number",
        "building": "building_code",
        "phone": "phone_number",
        "special_request": "request_text_or_none"
    }},
    "total_cost": total_amount,
    "confidence": "high/medium/low"
}}

If no confirmed order found, respond: {{"has_order": false}}"""

    try:
        # Send to LLM for analysis
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": analysis_prompt,
                "stream": False,
                "temperature": 0.1,  # Low temperature for consistent parsing
                "stop": ["\n\n", "User:", "Assistant:"]
            }
            
            response = await client.post(OLLAMA_URL, json=payload)
            if response.status_code == 200:
                result = response.json()
                llm_response = result.get("response", "").strip()
                
                debug_log(f"LLM analysis response: {llm_response}")
                
                # Try to parse JSON response
                try:
                    # Clean up response - sometimes LLM adds extra text
                    json_start = llm_response.find('{')
                    json_end = llm_response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = llm_response[json_start:json_end]
                        order_analysis = json.loads(json_text)
                        
                        debug_log(f"Parsed LLM analysis: {order_analysis}")
                        
                        # Validate the analysis
                        if order_analysis.get("has_order") and order_analysis.get("order_confirmed"):
                            # Additional validation
                            items = order_analysis.get("items", [])
                            customer_info = order_analysis.get("customer_info", {})
                            
                            if items and customer_info.get("rfid") and customer_info.get("building"):
                                # Format for our system
                                formatted_order = {
                                    "items": items,
                                    "total_cost": order_analysis.get("total_cost", 0),
                                    "rf_id": customer_info.get("rfid"),
                                    "building": customer_info.get("building"),
                                    "phone": customer_info.get("phone", "Not provided"),
                                    "special_request": customer_info.get("special_request", "None"),
                                    "is_complete": True,
                                    "rf_id_valid": True,
                                    "building_valid": True,
                                    "valid_phone": bool(customer_info.get("phone")),
                                    "confidence": order_analysis.get("confidence", "medium")
                                }
                                
                                debug_log(f"LLM extracted valid order: {formatted_order}")
                                return formatted_order
                        
                        debug_log("LLM analysis indicates no confirmed order")
                        return None
                        
                except json.JSONDecodeError as e:
                    debug_log(f"Failed to parse LLM JSON response: {e}")
                    debug_log(f"Raw response: {llm_response}")
                    return None
            else:
                debug_log(f"LLM request failed: {response.status_code}")
                return None
                
    except Exception as e:
        debug_log(f"Error in LLM conversation analysis: {e}")
        return None

async def detect_order_confirmation_and_save_with_llm(session_id: str, bot_response: str, user_message: str) -> bool:
    """
    Use LLM to detect and save confirmed orders
    Returns True if order was saved, False otherwise
    """
    debug_log(f"Using LLM to detect order confirmation")
    
    # Get conversation
    conversation = ConversationLogger.get_conversation(session_id)
    
    # Use LLM to analyze conversation
    order_data = await analyze_conversation_with_llm(conversation, session_id)
    
    if not order_data:
        debug_log("LLM found no confirmed order")
        return False
    
    debug_log("LLM DETECTED CONFIRMED ORDER!")
    
    # Save the order
    debug_log(f"SAVING LLM ORDER: Items: {len(order_data['items'])}, RFID: {order_data['rf_id']}, Building: {order_data['building']}, Total: {order_data['total_cost']}")
    save_final_order_to_file(order_data)
    
    # Clean up session
    order_state = get_or_create_order_state(session_id)
    order_state.reset()
    
    debug_log("Order saved successfully via LLM analysis")
    return True
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

class OrderState:
    def __init__(self):
        self.in_order_flow = False
        self.rf_id = None
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
            "rf_id": self.rf_id,
            "building": self.building,
            "phone": self.phone,
            "items": self.items,
            "total_cost": self.total_cost,
            "special_request": self.special_request
        }

# Global order state storage
order_states: Dict[str, OrderState] = {}

def quick_error_response(error_message: str) -> str:
    """Generate a quick error response without LLM processing"""
    return error_message

def get_or_create_order_state(session_id: str) -> OrderState:
    if session_id not in order_states:
        order_states[session_id] = OrderState()
    return order_states[session_id]

# FALLBACK ITEM EXTRACTION (kept as fallback)
async def extract_items_fallback(combined_text: str, bot_response: str) -> List[Dict]:
    """
    Enhanced fallback item extraction using MCP server for menu items
    """
    items = []
    
    print(f"[FALLBACK] Bot response: '{bot_response}'")
    print(f"[FALLBACK] Combined text: '{combined_text[:200]}...'")
    
    # Pattern 1: Bot summary format "- Item: X\n- Price: AED Y" (separate lines)
    item_pattern = r'-\s*Item:\s*([^\n]+)'
    price_pattern = r'-\s*Price:\s*AED\s*([\d.]+)'
    
    item_match = re.search(item_pattern, bot_response, re.IGNORECASE)
    price_match = re.search(price_pattern, bot_response, re.IGNORECASE)
    
    if item_match and price_match:
        item_name = item_match.group(1).strip()
        price = float(price_match.group(1))
        
        # Try to extract quantity from conversation - look for specific quantity mentions
        qty = 1  # Default to 1
        
        # Look for quantity in conversation before the item mention
        qty_patterns = [
            r'(\d+)\s*' + re.escape(item_name.lower()),
            r'(\d+)\s*' + item_name.split()[0].lower() if item_name.split() else r'(\d+)',
            r'order\s*(\d+)',
            r'want\s*(\d+)',
            r'get\s*(\d+)'
        ]
        
        for pattern in qty_patterns:
            qty_match = re.search(pattern, combined_text.lower())
            if qty_match:
                try:
                    potential_qty = int(qty_match.group(1))
                    # Only use reasonable quantities (1-50)
                    if 1 <= potential_qty <= 50:
                        qty = potential_qty
                        print(f"[FALLBACK] Found quantity {qty} with pattern: {pattern}")
                        break
                except (ValueError, IndexError):
                    continue
        
        # Clean up item name
        if 'pizza' not in item_name.lower() and ('pepperoni' in item_name.lower() or 'margherita' in item_name.lower() or 'cheese' in item_name.lower()):
            item_name += ' Pizza'
        
        items.append({
            'name': item_name,
            'price': price,
            'quantity': qty,
            'total_price': price * qty
        })
        print(f"[FALLBACK] Extracted from bot summary: {qty}x {item_name} @ AED {price} = AED {price * qty}")
        return items
    
    # Pattern 2: Bot response with "X Item for total of AED Y"
    bot_order_pattern = r'(\d+)\s*([^f]*?)\s*for.*?total.*?AED\s*([\d.]+)'
    bot_match = re.search(bot_order_pattern, bot_response, re.IGNORECASE)
    
    if bot_match:
        qty = int(bot_match.group(1))
        item_text = bot_match.group(2).strip()
        total_price = float(bot_match.group(3))
        price_per_item = total_price / qty
        
        # Clean up item name
        item_name = item_text.replace('pizzas', 'Pizza').replace('pizza', 'Pizza').title()
        
        items.append({
            'name': item_name,
            'price': price_per_item,
            'quantity': qty,
            'total_price': total_price
        })
        print(f"[FALLBACK] Extracted from bot order: {qty}x {item_name} @ AED {price_per_item} = AED {total_price}")
        return items
    
    # Pattern 3: "X x Y.0 + Z x W.0" calculation format
    calculation_pattern = r'(\d+)\s*x\s*([\d.]+)\s*\+\s*(\d+)\s*x\s*([\d.]+)'
    calc_match = re.search(calculation_pattern, bot_response)
    
    if calc_match:
        print(f"[FALLBACK] Found calculation: {calc_match.groups()}")
        qty1, price1, qty2, price2 = calc_match.groups()
        
        # Try to find what items these refer to using MCP
        bot_text_before_calc = bot_response[:calc_match.start()]
        
        if 'pepperoni' in bot_text_before_calc.lower():
            # Query MCP for pepperoni details
            pepperoni_item = await fetch_menu_item_from_mcp("Pepperoni Pizza")
            if pepperoni_item:
                items.append({
                    'name': pepperoni_item['name'],
                    'price': pepperoni_item['price'],
                    'quantity': int(qty1),
                    'total_price': pepperoni_item['price'] * int(qty1)
                })
            else:
                items.append({
                    'name': 'Pepperoni Pizza',
                    'price': float(price1),
                    'quantity': int(qty1),
                    'total_price': float(price1) * int(qty1)
                })
            print(f"[FALLBACK] Added Pepperoni Pizza: {int(qty1)}x AED {price1}")
        
        if 'french fries' in bot_text_before_calc.lower():
            # Query MCP for fries details
            fries_item = await fetch_menu_item_from_mcp("French Fries")
            if fries_item:
                items.append({
                    'name': fries_item['name'],
                    'price': fries_item['price'],
                    'quantity': int(qty2),
                    'total_price': fries_item['price'] * int(qty2)
                })
            else:
                items.append({
                    'name': 'French Fries',
                    'price': float(price2),
                    'quantity': int(qty2),
                    'total_price': float(price2) * int(qty2)
                })
            print(f"[FALLBACK] Added French Fries: {int(qty2)}x AED {price2}")
        
        return items
    
    # Pattern 4: Extract from conversation and query MCP
    print("[FALLBACK] No bot patterns found, trying conversation extraction with MCP...")
    
    # Extract potential item names from conversation
    conversation_patterns = [
        # Enhanced patterns to handle more variations
        r'i\s*want\s*to\s*get\s*a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my\s+rfid|\s+rfid|\s+building|\s+phone|\s*$)',
        r'i\s*want\s*to\s*order\s*a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my\s+rfid|\s+rfid|\s+building|\s+phone|\s*$)',
        r'order\s*a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my\s+rfid|\s+rfid|\s+building|\s+phone|\s*$)',
        r'get\s*a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my\s+rfid|\s+rfid|\s+building|\s+phone|\s*$)',
        r'(\d+)\s+([a-zA-Z\s]+?)(?:\s+my\s+rfid|\s+rfid|\s+building|\s+phone|\s*$)',
        
        # More flexible patterns for different sentence structures
        r'want\s+a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my|\s+rfid|\s+building|\s+phone)',
        r'get\s+a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my|\s+rfid|\s+building|\s+phone)',
        r'order\s+a?\s*([a-zA-Z\s]+?)(?:\s+yes|\s+\d+|\s+my|\s+rfid|\s+building|\s+phone)',
        
        # Pattern specifically for "Chicken Dynamite" style names
        r'([A-Z][a-zA-Z]*\s+[A-Z][a-zA-Z]*)',  # Captures "Chicken Dynamite"
    ]
    
    # Extract quantities separately
    quantity_patterns = [
        r'i\s+want\s+(\d+)\s+of\s+them',
        r'(\d+)\s+of\s+them',
        r'want\s+(\d+)',
        r'get\s+(\d+)',
        r'order\s+(\d+)',
    ]
    
    # Find potential item names
    potential_items = []
    potential_quantity = 1
    
    text_to_search = combined_text.lower()
    
    # Extract quantity first
    for pattern in quantity_patterns:
        qty_match = re.search(pattern, text_to_search)
        if qty_match:
            try:
                qty = int(qty_match.group(1))
                if 1 <= qty <= 50:  # Reasonable range
                    potential_quantity = qty
                    print(f"[FALLBACK] Found quantity: {potential_quantity}")
                    break
            except (ValueError, IndexError):
                continue
    
    # Extract item names
    for pattern in conversation_patterns:
        print(f"[FALLBACK] Trying pattern: {pattern}")
        matches = re.findall(pattern, text_to_search, re.IGNORECASE)
        print(f"[FALLBACK] Pattern matches: {matches}")
        
        for match in matches:
            if isinstance(match, tuple):
                # Handle patterns like r'(\d+)\s+([a-zA-Z\s]+?)'
                if len(match) == 2:
                    if match[0].isdigit():
                        qty_candidate = int(match[0])
                        if 1 <= qty_candidate <= 50:
                            potential_quantity = qty_candidate
                        item_candidate = match[1].strip()
                    else:
                        item_candidate = match[0].strip()
                else:
                    item_candidate = match[0].strip() if match else ""
            else:
                item_candidate = match.strip()
            
            # Clean up item name
            item_candidate = item_candidate.strip()
            
            # Skip obvious non-items
            if (item_candidate in ['of', 'them', 'my', 'rfid', 'building', 'phone', 'number', 'a', 'the', 'yes'] 
                or len(item_candidate) < 3 or item_candidate.isdigit()):
                print(f"[FALLBACK] Skipping obvious non-item: '{item_candidate}'")
                continue
            
            print(f"[FALLBACK] Found potential item: '{item_candidate}'")
            potential_items.append(item_candidate)
            
        # If we found any items from this pattern, stop trying other patterns
        if potential_items:
            break
    
    # Query MCP for each potential item
    for item_candidate in potential_items:
        print(f"[FALLBACK] Querying MCP for: '{item_candidate}'")
        
        # Try exact match first
        mcp_item = await fetch_menu_item_from_mcp(item_candidate)
        
        # If no exact match, try variations
        if not mcp_item:
            variations = [
                f"{item_candidate} Pizza",
                f"{item_candidate.title()}",
                f"{item_candidate.title()} Pizza",
                item_candidate.replace(" ", ""),
                item_candidate.capitalize(),
            ]
            
            for variation in variations:
                print(f"[FALLBACK] Trying variation: '{variation}'")
                mcp_item = await fetch_menu_item_from_mcp(variation)
                if mcp_item:
                    break
        
        if mcp_item:
            print(f"[FALLBACK] Found in MCP: {mcp_item['name']} - AED {mcp_item['price']}")
            items.append({
                'name': mcp_item['name'],
                'price': mcp_item['price'],
                'quantity': potential_quantity,
                'total_price': mcp_item['price'] * potential_quantity
            })
            print(f"[FALLBACK] Added from MCP: {potential_quantity}x {mcp_item['name']} @ AED {mcp_item['price']}")
            break  # Found one item, stop looking
        else:
            print(f"[FALLBACK] '{item_candidate}' not found in MCP")
    
    # Deduplicate items based on name (in case multiple patterns matched the same item)
    seen_items = {}
    deduplicated_items = []
    
    for item in items:
        item_name = item.get('name', '').lower()
        if item_name not in seen_items:
            seen_items[item_name] = True
            deduplicated_items.append(item)
        else:
            print(f"[FALLBACK] Skipping duplicate item: {item['name']}")
    
    print(f"[FALLBACK] Final items after deduplication: {deduplicated_items}")
    return deduplicated_items

# UNIFIED ORDER EXTRACTION FUNCTION
async def extract_complete_order_data(conversation: List[Dict], session_id: str = None, for_confirmation: bool = False) -> Optional[Dict]:
    """
    Unified order extraction function that handles both completion checking and confirmation extraction.
    
    Args:
        conversation: List of conversation messages
        session_id: Session ID for order state access
        for_confirmation: If True, prioritizes current order state and uses enhanced extraction for saving
    
    Returns:
        Dict with order data including items, rf_id, building, phone, special_request, validation status
    """
    debug_log(f"Extracting complete order data - for_confirmation={for_confirmation}, session_id={session_id}")
    
    user_messages = []
    bot_messages = []
    
    for msg in conversation:
        if msg['sender'] == 'user':
            user_messages.append(msg['message'])
        else:
            bot_messages.append(msg['message'])
    
    # Combine all user messages for analysis
    combined_text = " ".join(user_messages)
    latest_bot_response = bot_messages[-1] if bot_messages else ""
    
    debug_log(f"Analyzing combined text: '{combined_text[:200]}...'")
    
    # Get order state if available
    order_state = None
    if session_id:
        order_state = get_or_create_order_state(session_id)
    
    # Extract order items - prioritize order state for confirmations
    items = []
    if for_confirmation and order_state and order_state.items:
        items = order_state.items
        debug_log(f"Using items from order state: {[item.get('name', 'Unknown') for item in items]}")
    else:
        # Try RAG extraction first
        items = rag_extract_menu_items(combined_text)
        items = normalize_order_items(items)
        debug_log(f"RAG extracted {len(items)} items: {[item.get('name', 'Unknown') for item in items]}")
        
        # Use fallback if RAG failed
        if not items and for_confirmation:
            items = await extract_items_fallback(combined_text, latest_bot_response)
            debug_log(f"Fallback extracted {len(items)} items: {[item.get('name', 'Unknown') for item in items]}")
    
    # Extract RF ID with multiple patterns - prioritize order state for confirmations
    rf_id = None
    rf_id_valid = False
    
    if for_confirmation and order_state and order_state.rf_id:
        rf_id = order_state.rf_id
        rf_id_valid = True
        debug_log(f"Got RFID from order state: {rf_id}")
    else:
        # Try multiple RFID patterns
        rfid_patterns = [
            r'rfid.*?(\d{6})',
            r'rf.*?id.*?(\d{6})',
            r'\b(\d{6})\b',
            r'id.*?(\d{6})'
        ]
        
        for pattern in rfid_patterns:
            rfid_match = re.search(pattern, combined_text, re.IGNORECASE)
            if rfid_match:
                potential_rfid = rfid_match.group(1)
                if len(potential_rfid) == 6:
                    rf_id = potential_rfid
                    rf_id_valid = True
                    debug_log(f"Found RFID with pattern '{pattern}': {rf_id}")
                    break
        
        # Also check bot response for RFID
        if not rf_id and for_confirmation:
            bot_rfid_match = re.search(r'(\d{6})', latest_bot_response)
            if bot_rfid_match:
                rf_id = bot_rfid_match.group(1)
                rf_id_valid = True
                debug_log(f"Found RFID in bot response: {rf_id}")
    
    # Extract building - prioritize order state for confirmations
    building = None
    building_valid = False
    
    if for_confirmation and order_state and order_state.building:
        building = order_state.building
        building_valid = building in AVAILABLE_BUILDINGS
        debug_log(f"Got building from order state: {building}")
    else:
        building_match = re.search(r'\b([A-Z]\d[A-Z]?)\b', combined_text, re.IGNORECASE)
        if building_match:
            building = building_match.group(1).upper()
            building_valid = building in AVAILABLE_BUILDINGS
            debug_log(f"Got building from conversation: {building}")
        
        # Also check bot response
        if not building and for_confirmation:
            bot_building_match = re.search(r'building\s*([A-Z]\d[A-Z]?)', latest_bot_response, re.IGNORECASE)
            if bot_building_match:
                building = bot_building_match.group(1).upper()
                building_valid = building in AVAILABLE_BUILDINGS
                debug_log(f"Found building in bot response: {building}")
    
    # Extract phone with better patterns - prioritize order state for confirmations
    phone = None
    valid_phone = False
    
    if for_confirmation and order_state and order_state.phone:
        phone = order_state.phone
        valid_phone = True
        debug_log(f"Got phone from order state: {phone}")
    else:
        # Try multiple phone patterns
        phone_patterns = [
            r'phone.*?number.*?(\d{10})',
            r'phone.*?(\d{10})',
            r'number.*?(\d{10})',
            r'\b(05\d{8})\b',
            r'\b(\d{10})\b'
        ]
        
        # Check combined text first
        for pattern in phone_patterns:
            phone_match = re.search(pattern, combined_text.replace(' ', '').replace('-', ''), re.IGNORECASE)
            if phone_match:
                potential_phone = phone_match.group(1)
                if len(potential_phone) == 10 and potential_phone.startswith('05'):
                    phone = potential_phone
                    valid_phone = True
                    debug_log(f"Found phone in conversation: {phone}")
                    break
                elif len(potential_phone) == 10 and potential_phone.startswith('5'):
                    phone = '0' + potential_phone
                    valid_phone = True
                    debug_log(f"Found phone in conversation (added 0): {phone}")
                    break
        
        # Also check bot response
        if not phone and for_confirmation:
            bot_phone_match = re.search(r'phone.*?number.*?(\d{10})', latest_bot_response, re.IGNORECASE)
            if bot_phone_match:
                potential_phone = bot_phone_match.group(1)
                if len(potential_phone) == 10 and potential_phone.startswith('05'):
                    phone = potential_phone
                    valid_phone = True
                    debug_log(f"Found phone in bot response: {phone}")
                elif len(potential_phone) == 10 and potential_phone.startswith('5'):
                    phone = '0' + potential_phone
                    valid_phone = True
                    debug_log(f"Found phone in bot response (added 0): {phone}")
    
    # Extract special requests - prioritize order state for confirmations
    special_request = "None"
    if for_confirmation and order_state and order_state.special_request is not None:
        special_request = order_state.special_request
        debug_log(f"Got special request from order state: {special_request}")
    else:
        for msg in reversed(user_messages[-10:]):
            if any(keyword in msg.lower() for keyword in ['special', 'request', 'note', 'dietary', 'allergy']):
                if not any(word in msg.lower() for word in ['no', 'none', 'nothing']):
                    special_request = msg
                    break
    
    debug_log(f"Final extraction - Items: {len(items)}, RFID: {rf_id}, Building: {building}, Phone: {phone}")
    
    # Check if we have all required fields and they're valid
    has_all_fields = (items and rf_id_valid and building_valid and valid_phone)
    
    if items:
        order_data = {
            'items': items,
            'total_cost': sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items),
            'rf_id': rf_id,
            'building': building,
            'phone': phone,
            'special_request': special_request,
            'is_complete': has_all_fields,
            'rf_id_valid': rf_id_valid,
            'building_valid': building_valid,
            'valid_phone': valid_phone
        }
        
        # Track both missing and invalid fields
        missing_fields = []
        invalid_fields = []
        
        if not rf_id:
            missing_fields.append('rf_id')
        elif not rf_id_valid:
            invalid_fields.append('rf_id')
            
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

async def detect_order_confirmation_and_save(session_id: str, bot_response: str, user_message: str) -> bool:
    """
    Detect if the LLM just confirmed an order and save it to orders.txt
    Returns True if order was saved, False otherwise
    """
    debug_log(f"Checking bot response for order confirmation: '{bot_response[:100]}...'")
    
    # Look for order confirmation patterns in bot response
    confirmation_patterns = [
        r'thank you for.*order',
        r'order.*will be delivered',
        r'have a great day',
        r'enjoy your meal',
        r'order.*confirmed',
        r'order.*placed.*successfully',
        r'here\'?s a summary of your order',  # Added for your case
        r'your total is.*aed',  # Added for order summaries
        r'summary.*order.*aed',  # Another pattern for summaries
    ]
    
    is_confirmation = any(re.search(pattern, bot_response.lower()) for pattern in confirmation_patterns)
    
    if not is_confirmation:
        debug_log("No order confirmation detected")
        return False
    
    debug_log("ORDER CONFIRMATION DETECTED!")
    
    # Extract order details using unified function
    conversation = ConversationLogger.get_conversation(session_id)
    order_data = await extract_complete_order_data(conversation, session_id, for_confirmation=True)
    
    if not order_data:
        debug_log("No order data extracted")
        return False
    
    # Save if we have essential information
    if order_data['items'] and order_data['rf_id_valid'] and order_data['building_valid']:
        debug_log(f"SAVING ORDER: Items: {len(order_data['items'])}, RFID: {order_data['rf_id']}, Building: {order_data['building']}, Total: {order_data['total_cost']}")
        save_final_order_to_file(order_data)
        
        # Clean up session
        order_state = get_or_create_order_state(session_id)
        order_state.reset()
        
        return True
    else:
        debug_log(f"CANNOT SAVE - Missing essential info - Items: {len(order_data.get('items', []))}, RFID: {order_data['rf_id_valid']}, Building: {order_data['building_valid']}")
        return False

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

def check_for_order_completion(session_id: str) -> Optional[str]:
    """Check if an order can be completed"""
    order_state = get_or_create_order_state(session_id)
    
    if not order_state.in_order_flow:
        return None
    
    # Check if all required information is valid
    if (order_state.rf_id and 
        order_state.building and order_state.building in AVAILABLE_BUILDINGS and
        order_state.phone):
        
        # Format order data for saving
        order_data = {
            'items': order_state.items,
            'total_cost': order_state.total_cost,
            'rf_id': order_state.rf_id,
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
    Main chat endpoint with pre-validation + LLM approach
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

    # Log the user message
    ConversationLogger.log_message(session_id, user_message, "user")
    
    # Get order state
    order_state = get_or_create_order_state(session_id)
    print(f"DEBUG ORDER STATE BEFORE: RFID={order_state.rf_id}, Building={order_state.building}, Phone={order_state.phone}, InFlow={order_state.in_order_flow}")
    
    # PRE-VALIDATION - Check formats BEFORE LLM processing (runs for ALL order-related messages)
    if order_state.in_order_flow or re.search(r'\b(rf|rfid|building|phone|05\d{8}|\d{4,7}|[A-Z]\d[A-Z]?)\b', user_message, re.IGNORECASE):
        debug_log(f"PRE-VALIDATION TRIGGERED for message: '{user_message}'")
        validation_error = validate_and_update_order_state(user_message, order_state)
        if validation_error:
            debug_log(f"VALIDATION ERROR: {validation_error}")
            async def validation_error_stream():
                yield validation_error
            
            # Log the error response
            ConversationLogger.log_message(session_id, validation_error, "bot")
            return StreamingResponse(validation_error_stream(), media_type="text/plain")
        else:
            debug_log("No validation errors found") 
    else:
        debug_log("PRE-VALIDATION NOT TRIGGERED")
    print(f"DEBUG ORDER STATE AFTER: RFID={order_state.rf_id}, Building={order_state.building}, Phone={order_state.phone}, InFlow={order_state.in_order_flow}")
    
    # Process background order detection (keep existing code)
    await BackgroundOrderProcessor.process_session_orders(session_id)
    
    # Check for special request responses (keep existing code)
    if order_state.in_order_flow and order_state.special_request is None:
        user_message_lower = user_message.lower().strip()
        if user_message_lower in ['no', 'none', 'n/a', 'no special requests', 'nothing', 'don\'t have any special requests', 'i don\'t have any special requests']:
            order_state.special_request = 'None'
        elif not re.search(r'\b(rf|id|building|phone|number)\b', user_message_lower):
            # If message doesn't look like other order info, treat as special request
            order_state.special_request = user_message.strip()
    
    # Check for explicit order cancellation
    direct_response = check_for_direct_order_response(session_id, user_message)
    if direct_response:
        async def direct_response_stream():
            yield direct_response
        
        ConversationLogger.log_message(session_id, direct_response, "bot")
        return StreamingResponse(direct_response_stream(), media_type="text/plain")
    
    # Extract current order state from conversation (for order changes) - USE UNIFIED FUNCTION
    conversation_order_data = await extract_complete_order_data(ConversationLogger.get_conversation(session_id), session_id)
    
    # Sync conversation changes with session state
    if conversation_order_data and order_state.in_order_flow:
        # Update session state with any order changes from conversation
        if conversation_order_data.get('items') != order_state.items:
            print(f"DEBUG: Order items changed via conversation analysis")
            order_state.items = conversation_order_data['items']
            order_state.total_cost = conversation_order_data['total_cost']
    
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
                    yield f"[Looking up '{category_name}' in the menu...]\n"
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
        if open_restaurants_context:
            prompt += f"\n\n{open_restaurants_context}"
        prompt += f"\n{history_prompt}User: {user_message}\nAssistant:"

        # Add order state context if in order flow - SINGLE SOURCE OF TRUTH
        order_state = get_or_create_order_state(session_id)
        
        if order_state.in_order_flow:
            order_status = "\n[[CURRENT ORDER STATUS]]\n"
            items_inner = ', '.join([
                f"{item.get('quantity', 1)}x {item['name']}"
                for item in (order_state.items or [])
                if isinstance(item, dict) and 'name' in item
            ])
            order_status += f"Items: {items_inner}\n"
            order_status += f"Total: AED {order_state.total_cost:.2f}\n"
            
            # Show provided information
            order_status += "\nAlready Provided:\n"
            if order_state.rf_id:
                order_status += f"✓ RF ID: {order_state.rf_id}\n"
            if order_state.building:
                order_status += f"✓ Building: {order_state.building}\n"
            if order_state.phone:
                order_status += f"✓ Phone: {order_state.phone}\n"
            if order_state.special_request is not None:
                order_status += f"✓ Special Request: {order_state.special_request}\n"
            
            # Show still missing information
            order_status += "\nStill Missing:\n"
            if not order_state.rf_id:
                order_status += "- RF ID (must be 6 digits)\n"
            if not order_state.building:
                order_status += f"- Building (must be one of: {', '.join(AVAILABLE_BUILDINGS)})\n"
            if not order_state.phone:
                order_status += "- Phone number (must be a valid UAE mobile number)\n"
            if order_state.special_request is None:
                order_status += "- Special Request (ask if they have any special requests, dietary restrictions, etc.)\n"
            
            # Insert the order status at the beginning of the prompt for priority
            prompt = order_status + "\n" + prompt
            
            # Add validation tools to the payload
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "tools": VALIDATION_TOOLS,
                "stop": ["User:", "Assistant:", "\nUser:", "\nAssistant:"],
                "temperature": 0.1  # Lower temperature for more consistent responses
            }

        else:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "stop": ["User:", "Assistant:", "\nUser:", "\nAssistant:"],
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
                            elif "tool_calls" in data:
                                # Handle tool calls
                                for tool_call in data["tool_calls"]:
                                    function_name = tool_call["function"]["name"]
                                    function_args = json.loads(tool_call["function"]["arguments"])
                                    
                                    if function_name in VALIDATION_FUNCTIONS:
                                        result = VALIDATION_FUNCTIONS[function_name](**function_args)
                                        
                                        # Update order state based on validation results
                                        if result["valid"]:
                                            if function_name == "validate_rf_id":
                                                order_state.rf_id = result["rf_id"]
                                            elif function_name == "validate_phone_number":
                                                order_state.phone = result["phone"]
                                            elif function_name == "validate_building":
                                                order_state.building = result["building"]
                                        
                                        # Add validation result to prompt context
                                        prompt += f"\n[[VALIDATION RESULT]]\n{json.dumps(result)}\n"
                                        
                                        # Get model's response to the validation
                                        validation_response = await client.post(
                                            OLLAMA_URL,
                                            json={"model": OLLAMA_MODEL, "prompt": prompt, "stop": ["\nUser:", "\nAssistant:", "User:", "Assistant:", "\n\nUser:", "\n\nAssistant:"], "temperature": 0.25}
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
            debug_log(f"Bot response complete: '{bot_response[:100]}...'")
            ConversationLogger.log_message(session_id, bot_response, "bot")
            
            # Try regex-based detection first (for backwards compatibility)
            debug_log("Calling detect_order_confirmation_and_save...")
            saved = await detect_order_confirmation_and_save(session_id, bot_response, user_message)
            debug_log(f"Regex order save result: {saved}")
            
            # If regex didn't work, try LLM analysis
            if not saved:
                debug_log("Regex detection failed, trying LLM analysis...")
                saved_llm = await detect_order_confirmation_and_save_with_llm(session_id, bot_response, user_message)
                debug_log(f"LLM order save result: {saved_llm}")
            else:
                debug_log("Order already saved via regex detection")

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
            "stop": ["User:", "Assistant:", "\nUser:", "\nAssistant:"],
            "temperature": 0.25
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
async def test_order_changes(session_id: str):
    """Debug endpoint to test order change detection"""
    
    # Clear existing conversation
    ConversationLogger.cleanup_session(session_id)
    
    # Simulate conversation with order changes
    test_conversation = [
        ("user", "hi, do you have burgers?"),
        ("bot", "Yes, we have burgers for AED 25 each"),
        ("user", "I want 5 burgers"),
        ("bot", "Great! 5 burgers for AED 125. Please provide your RF ID"),
        ("user", "actually, I want 3 burgers instead"),
        ("user", "my rf id is 123456"),
        ("user", "building A1A"),
        ("user", "phone 971501234567"),
        ("user", "no special requests")
    ]
    
    # Log all messages
    for sender, message in test_conversation:
        ConversationLogger.log_message(session_id, message, sender)
    
    # Extract final order data using unified function
    conversation = ConversationLogger.get_conversation(session_id)
    order_data = await extract_complete_order_data(conversation, session_id)
    
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

@app.post('/debug/analyze_conversation/{session_id}')
async def debug_analyze_conversation(session_id: str):
    """Debug endpoint to test LLM conversation analysis"""
    conversation = ConversationLogger.get_conversation(session_id)
    
    if not conversation:
        return {
            "error": "No conversation found for session",
            "session_id": session_id
        }
    
    # Analyze with LLM
    order_data = await analyze_conversation_with_llm(conversation, session_id)
    
    return {
        "session_id": session_id,
        "conversation_length": len(conversation),
        "llm_analysis": order_data,
        "has_confirmed_order": order_data is not None,
        "conversation_preview": [
            f"{msg['sender']}: {msg['message'][:100]}..."
            for msg in conversation[-5:]  # Last 5 messages
        ]
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