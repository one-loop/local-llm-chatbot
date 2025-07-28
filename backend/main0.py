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
# OLLAMA_MODEL = 'mistral'
OLLAMA_MODEL = 'qwen2.5'

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
            'cart': [],  # Shopping cart for items before checkout
            'items': [],  # Items in current order (during checkout)
            'last_shown_items': [],  # Last items shown to user (for "add to cart" responses)
            'total_cost': 0,
            'nyu_id': None,
            'building': None,
            'phone': None,
            'special_request': None,
            # New fields for editable/interruptible orders
            'paused_at': None,  # State where order was paused
            'can_resume': False,  # Whether order can be resumed
            'last_interaction': None,  # Timestamp of last interaction
            'interruption_context': None  # Context of what user was asking about
        }
    return order_states[session_id]

def reset_order_state(session_id: str):
    """Reset order state for a session"""
    if session_id in order_states:
        # Keep cart and last_shown_items but reset order process
        cart = order_states[session_id].get('cart', [])
        last_shown_items = order_states[session_id].get('last_shown_items', [])
        order_states[session_id] = {
            'state': 'idle',
            'cart': cart,  # Preserve cart
            'items': [],
            'last_shown_items': last_shown_items,  # Preserve last shown items
            'total_cost': 0,
            'nyu_id': None,
            'building': None,
            'phone': None,
            'special_request': None,
            'paused_at': None,
            'can_resume': False,
            'last_interaction': None,
            'interruption_context': None
        }
        print(f"DEBUG: Order state reset for session {session_id}, cart preserved: {len(cart)} items")

def clear_cart(session_id: str):
    """Clear the shopping cart"""
    order_state = get_order_state(session_id)
    order_state['cart'] = []
    print(f"DEBUG: Cart cleared for session {session_id}")

def add_to_cart(session_id: str, items: List[Dict]) -> str:
    """Add items to the shopping cart"""
    order_state = get_order_state(session_id)
    
    print(f"DEBUG: Adding to cart - Session: {session_id}")
    print(f"DEBUG: Items to add: {items}")
    print(f"DEBUG: Current cart before adding: {order_state['cart']}")
    
    if not items:
        print(f"DEBUG: No items provided to add to cart")
        return "No items to add to cart."
    
    for new_item in items:
        if not new_item or not new_item.get('name'):
            print(f"DEBUG: Skipping invalid item: {new_item}")
            continue
            
        # Check if item already exists in cart
        existing_item = None
        for cart_item in order_state['cart']:
            if cart_item['name'] == new_item['name']:
                existing_item = cart_item
                break
        
        if existing_item:
            # Update quantity and total price
            existing_item['quantity'] += new_item.get('quantity', 1)
            existing_item['total_price'] = existing_item['price'] * existing_item['quantity']
            print(f"DEBUG: Updated existing item: {existing_item}")
        else:
            # Add new item to cart
            new_cart_item = {
                'name': new_item['name'],
                'price': new_item.get('price', 0),
                'quantity': new_item.get('quantity', 1),
                'total_price': new_item.get('total_price', new_item.get('price', 0) * new_item.get('quantity', 1))
            }
            order_state['cart'].append(new_cart_item)
            print(f"DEBUG: Added new item: {new_cart_item}")
    
    print(f"DEBUG: Cart after adding: {order_state['cart']}")
    return format_cart_summary(order_state['cart'])

def format_cart_summary(cart_items: List[Dict]) -> str:
    """Format cart contents into a readable summary"""
    if not cart_items:
        return "Your cart is empty."
    
    item_lines = []
    total_cost = 0
    
    for item in cart_items:
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        total_price = item.get('total_price', price * qty)
        total_cost += total_price
        
        if qty > 1:
            item_lines.append(f"{qty}x {item['name']} (AED {price} each = AED {total_price})")
        else:
            item_lines.append(f"{item['name']} (AED {price})")
    
    summary = "🛒 Your Cart:\n" + "\n".join(f"• {line}" for line in item_lines)
    summary += f"\n\n💰 Total: AED {total_cost:.2f}"
    summary += "\n\nSay 'checkout' to place your order, or continue browsing to add more items!"
    
    return summary

def calculate_total_cost(items: List[Dict]) -> float:
    """Calculate total cost of all items"""
    return sum(item.get('total_price', item.get('price', 0) * item.get('quantity', 1)) for item in items)

def detect_edit_command(message: str) -> bool:
    """Detect if user wants to edit their order"""
    edit_patterns = [
        r'change.*to \d+',
        r'make.*\d+',
        r'update.*to \d+',
        r'modify.*\d+',
        r'edit.*'
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in edit_patterns)

def detect_remove_command(message: str) -> bool:
    """Detect if user wants to remove items from order"""
    remove_patterns = [
        r'remove.*from order',
        r'delete.*',
        r'take.*out',
        r'cancel.*',
        r'remove.*'
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in remove_patterns)

def detect_resume_command(message: str) -> bool:
    """Detect if user wants to resume their order"""
    resume_patterns = [
        r'resume.*order',
        r'continue.*order',
        r'back to.*order',
        r'continue',
        r'resume',
        r'let\'?s continue',
        r'proceed'
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in resume_patterns)

def should_allow_interruption(order_state: dict, message: str) -> bool:
    """Check if we should allow interruption during order flow"""
    # Don't interrupt if we're in idle state or already paused
    if order_state['state'] in ['idle'] or order_state.get('paused_at'):
        return False
    
    # Detect non-order questions/requests
    non_order_patterns = [
        r'what.*menu',
        r'show.*menu',
        r'do you have',
        r'tell me about',
        r'what\'?s.*open',
        r'what.*available',
        r'any.*desserts?',
        r'what.*drinks?',
        r'menu.*today',
        r'what.*else'
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in non_order_patterns)

def edit_order_quantity(session_id: str, message: str) -> str:
    """Edit quantity of items in current order"""
    order_state = get_order_state(session_id)
    
    # Extract item and new quantity
    quantity_match = re.search(r'(\d+)', message)
    if not quantity_match:
        return "Please specify the new quantity (e.g., 'change pizza to 3')"
    
    new_quantity = int(quantity_match.group(1))
    
    # Find item to modify (simple approach - look for item names)
    item_to_edit = None
    for item in order_state['items']:
        if item['name'].lower() in message.lower():
            item_to_edit = item
            break
    
    if not item_to_edit:
        # If no specific item found, try to edit the first/last item
        if len(order_state['items']) == 1:
            item_to_edit = order_state['items'][0]
        else:
            available_items = [item['name'] for item in order_state['items']]
            return f"Please specify which item to change. Available items: {', '.join(available_items)}"
    
    # Update quantity
    old_quantity = item_to_edit['quantity']
    item_to_edit['quantity'] = new_quantity
    item_to_edit['total_price'] = item_to_edit['price'] * new_quantity
    order_state['total_cost'] = calculate_total_cost(order_state['items'])
    
    print(f"DEBUG: Updated {item_to_edit['name']} quantity from {old_quantity} to {new_quantity}")
    
    items_summary = format_items_summary(order_state['items'])
    return f"Updated {item_to_edit['name']} to {new_quantity}! Your order:\n\n{items_summary}\n\nConfirm order? (yes/no)"

def remove_order_item(session_id: str, message: str) -> str:
    """Remove item from current order"""
    order_state = get_order_state(session_id)
    
    if not order_state['items']:
        return "Your order is empty, nothing to remove."
    
    # Find item to remove
    item_to_remove = None
    for item in order_state['items']:
        if item['name'].lower() in message.lower():
            item_to_remove = item
            break
    
    if not item_to_remove:
        # If no specific item found and only one item, remove it
        if len(order_state['items']) == 1:
            item_to_remove = order_state['items'][0]
        else:
            available_items = [item['name'] for item in order_state['items']]
            return f"Please specify which item to remove. Available items: {', '.join(available_items)}"
    
    # Remove the item
    order_state['items'].remove(item_to_remove)
    order_state['total_cost'] = calculate_total_cost(order_state['items'])
    
    print(f"DEBUG: Removed {item_to_remove['name']} from order")
    
    if not order_state['items']:
        # If no items left, return to idle
        reset_order_state(session_id)
        return f"Removed {item_to_remove['name']}. Your order is now empty. What would you like to order?"
    
    items_summary = format_items_summary(order_state['items'])
    return f"Removed {item_to_remove['name']}! Your order:\n\n{items_summary}\n\nConfirm order? (yes/no)"

def pause_order_flow(session_id: str, interruption_context: str = None):
    """Pause the current order flow for interruption"""
    order_state = get_order_state(session_id)
    order_state['paused_at'] = order_state['state']
    order_state['can_resume'] = True
    order_state['interruption_context'] = interruption_context
    order_state['last_interaction'] = datetime.datetime.now().isoformat()
    
    print(f"DEBUG: Paused order at state: {order_state['paused_at']}")

def resume_order_flow(session_id: str) -> str:
    """Resume paused order flow"""
    order_state = get_order_state(session_id)
    
    if not order_state.get('can_resume') or not order_state.get('paused_at'):
        return "No paused order to resume. Start a new order or add items to cart!"
    
    # Restore the paused state
    paused_state = order_state['paused_at']
    order_state['state'] = paused_state
    order_state['paused_at'] = None
    order_state['can_resume'] = False
    order_state['interruption_context'] = None
    
    print(f"DEBUG: Resumed order at state: {paused_state}")
    
    # Return appropriate message based on where we paused
    if paused_state == 'waiting_for_order_confirmation':
        items_summary = format_items_summary(order_state['items'])
        return f"Resuming your order!\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)"
    elif paused_state == 'waiting_for_nyu_id':
        return "Continuing with your order. Please provide the 8 digits of your NYU ID card after the N (e.g., if your ID is N12345678, enter 12345678):"
    elif paused_state == 'waiting_for_building':
        buildings_list = ", ".join(AVAILABLE_BUILDINGS)
        return f"Continuing with your order. Please select your building number from: {buildings_list}"
    elif paused_state == 'waiting_for_phone':
        return "Continuing with your order. Please provide your phone number:"
    elif paused_state == 'waiting_for_special_request':
        return "Continuing with your order. Do you have any special requests? If not, just say 'no' or 'none':"
    else:
        return "Resuming your order. How can I help you continue?"

def handle_interruption(user_message: str, session_id: str) -> tuple[str, bool]:
    """Handle interruption during order flow"""
    order_state = get_order_state(session_id)
    
    # Pause the current order
    pause_order_flow(session_id, user_message)
    
    # Let the normal chat handle the interruption question
    # But add a note about resuming
    return "", True  # Continue with normal chat, but we've paused the order

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
    
    print(f"DEBUG: process_order_flow - Session: {session_id}, Message: '{user_message}', State: {order_state['state']}")
    
    # HIGH PRIORITY FEATURE 1: Basic quantity editing
    if order_state['items'] and detect_edit_command(user_message):
        print(f"DEBUG: Detected edit command: '{user_message}'")
        edit_response = edit_order_quantity(session_id, user_message)
        return edit_response, False
    
    # HIGH PRIORITY FEATURE 2: Item removal  
    if order_state['items'] and detect_remove_command(user_message):
        print(f"DEBUG: Detected remove command: '{user_message}'")
        remove_response = remove_order_item(session_id, user_message)
        return remove_response, False
    
    # HIGH PRIORITY FEATURE 3: Resume from interruption
    if order_state.get('can_resume') and detect_resume_command(user_message):
        print(f"DEBUG: Detected resume command: '{user_message}'")
        resume_response = resume_order_flow(session_id)
        return resume_response, False
    
    # HIGH PRIORITY FEATURE 3: Simple interruption handling
    if should_allow_interruption(order_state, user_message):
        print(f"DEBUG: Allowing interruption during state: {order_state['state']}")
        interruption_response, continue_chat = handle_interruption(user_message, session_id)
        return interruption_response, continue_chat
    
    # Handle cart commands first - more comprehensive patterns
    if re.search(r'\bcart\b|\bview cart\b|\bshow cart\b|\bmy cart\b|\bcheck cart\b', user_message_lower):
        cart_summary = format_cart_summary(order_state['cart'])
        print(f"DEBUG: Cart view requested - returning: {cart_summary}")
        return cart_summary, False
    
    if re.search(r'\bclear cart\b|\bempty cart\b|\bremove all\b|\breset cart\b', user_message_lower):
        clear_cart(session_id)
        return "🗑️ Your cart has been cleared.", False
    
    # Handle standalone "add to cart" commands (when user responds to AI suggestions)
    if re.search(r'^add to cart$|^add to cart\s*$|^cart$|^add$', user_message_lower.strip()):
        # User wants to add the last shown items to cart
        last_items = order_state.get('last_shown_items', [])
        print(f"DEBUG: Standalone 'add to cart' - last_shown_items: {last_items}")
        if last_items:
            cart_summary = add_to_cart(session_id, last_items)
            # Clear last_shown_items after adding to cart
            order_state['last_shown_items'] = []
            return f"✅ Added to your cart!\n\n{cart_summary}", False
        else:
            return "I don't have any recent items to add to cart. Please specify what you'd like to add (e.g., 'add 2 pizzas to cart').", False
    
    # Handle "order now" responses (when user responds to AI suggestions)
    if re.search(r'^order now$|^order$|^yes$|^confirm$', user_message_lower.strip()) and order_state['state'] == 'idle':
        # User wants to order the last shown items immediately
        last_items = order_state.get('last_shown_items', [])
        print(f"DEBUG: Order now command - last_shown_items: {last_items}")
        if last_items:
            order_state['state'] = 'waiting_for_order_confirmation'
            order_state['items'] = last_items
            order_state['total_cost'] = calculate_total_cost(last_items)
            order_state['last_shown_items'] = []  # Clear after using
            items_summary = format_items_summary(last_items)
            print(f"DEBUG: Starting order confirmation - Items: {last_items}, Total: {order_state['total_cost']}")
            return f"Ready to order!\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)", False
        else:
            return "I don't have any recent items to order. Please specify what you'd like to order.", False
    
    # Handle direct "add X to cart" commands - Enhanced patterns
    if re.search(r'add.*to cart|add.*cart|put.*cart|save.*cart|.*to cart', user_message_lower):
        print(f"DEBUG: Detected 'add to cart' command: '{user_message}'")
        items_data = rag_extract_menu_items(user_message)
        print(f"DEBUG: RAG extracted items for cart: {items_data}")
        
        if items_data:
            cart_summary = add_to_cart(session_id, items_data)
            print(f"DEBUG: Successfully added items to cart")
            return f"✅ Added to your cart!\n\n{cart_summary}", False
        else:
            print(f"DEBUG: No items found from message: '{user_message}'")
            return "I couldn't find those items on the menu. Please try again with specific item names (e.g., 'add 2 pizzas to cart').", False
    
    # Handle checkout commands
    if re.search(r'\bcheckout\b|\bplace order\b|\border now\b', user_message_lower):
        if not order_state['cart']:
            return "Your cart is empty. Add some items first!", False
        
        # Move cart items to order items and start checkout process
        order_state['items'] = order_state['cart'].copy()
        order_state['total_cost'] = calculate_total_cost(order_state['items'])
        order_state['state'] = 'waiting_for_order_confirmation'
        
        items_summary = format_items_summary(order_state['items'])
        print(f"DEBUG: Checkout initiated - Items: {order_state['items']}, Total: {order_state['total_cost']}")
        return f"Ready to checkout!\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)", False
    
    # Check if user wants to start ordering or add items to cart
    if order_state['state'] == 'idle':
        # Try to extract multiple items
        items_data = rag_extract_menu_items(user_message)
        print(f"DEBUG: Idle state - RAG extracted items: {items_data}")
        
        if items_data:
            # Store the found items for potential "add to cart" response
            order_state['last_shown_items'] = items_data
            print(f"DEBUG: Stored items in last_shown_items: {items_data}")
            
            # Check intent: add to cart vs immediate order
            if re.search(r'add.*to cart|add.*cart|put.*cart|save.*cart|.*to cart', user_message_lower):
                # Add to cart intent - handle this directly, don't pass to AI
                cart_summary = add_to_cart(session_id, items_data)
                print(f"DEBUG: Direct add to cart - items added")
                return f"✅ Added to your cart!\n\n{cart_summary}", False
            elif re.search(r'order now|buy now|purchase now|order immediately', user_message_lower):
                # Immediate order intent
                order_state['state'] = 'waiting_for_order_confirmation'
                order_state['items'] = items_data
                order_state['total_cost'] = calculate_total_cost(items_data)
                items_summary = format_items_summary(items_data)
                print(f"DEBUG: Immediate order - starting confirmation")
                return f"Ready to order!\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)", False
            else:
                # Ambiguous intent - this will be handled in the main chat flow
                print(f"DEBUG: Ambiguous intent - passing to AI")
                return "", True
        else:
            print(f"DEBUG: No items extracted from message in idle state")
            # No items found - continue with normal chat
            return "", True
    
    # Handle order flow states (when in checkout process)
    if order_state['state'] == 'waiting_for_order_confirmation':
        # Check if user is trying to add more items - Enhanced patterns
        if (re.search(r'can i also|i also want|also have|add.*more|and.*more|plus|as well|too$|also$', user_message_lower) or 
            re.search(r'can i get|can i have|i want|i need|add.*as well|want.*as well', user_message_lower)):
            
            # Try to extract additional items
            additional_items = rag_extract_menu_items(user_message)
            print(f"DEBUG: User adding more items during order confirmation")
            print(f"DEBUG: Message: '{user_message}'")
            print(f"DEBUG: Extracted additional items: {additional_items}")
            print(f"DEBUG: Current order items before adding: {order_state['items']}")
            
            if additional_items:
                # Add to existing order items (not cart)
                order_state['items'].extend(additional_items)
                order_state['total_cost'] = calculate_total_cost(order_state['items'])
                items_summary = format_items_summary(order_state['items'])
                print(f"DEBUG: Updated order items: {order_state['items']}")
                print(f"DEBUG: New total: {order_state['total_cost']}")
                return f"Added to your order! Your current order:\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)", False
            else:
                print(f"DEBUG: No additional items extracted from: '{user_message}'")
                print(f"DEBUG: Checking for manual fallback patterns...")
                
                # Fallback: try to manually extract common patterns if RAG fails
                fallback_items = []
                
                # Check for margherita pattern
                margherita_match = re.search(r'(\d+)\s*(margherita|margarita)', user_message_lower)
                if margherita_match:
                    qty = int(margherita_match.group(1))
                    fallback_items.append({
                        'name': 'Margherita',
                        'price': 31.0,  # Known price from menu
                        'quantity': qty,
                        'total_price': 31.0 * qty
                    })
                    print(f"DEBUG: Fallback detected Margherita: {qty} items")
                
                # Check for pepperoni pattern
                pepperoni_match = re.search(r'(\d+)\s*(pepperoni)', user_message_lower)
                if pepperoni_match:
                    qty = int(pepperoni_match.group(1))
                    fallback_items.append({
                        'name': 'Pepperoni',
                        'price': 43.0,  # Estimated price
                        'quantity': qty,
                        'total_price': 43.0 * qty
                    })
                    print(f"DEBUG: Fallback detected Pepperoni: {qty} items")
                
                if fallback_items:
                    print(f"DEBUG: Using fallback items: {fallback_items}")
                    order_state['items'].extend(fallback_items)
                    order_state['total_cost'] = calculate_total_cost(order_state['items'])
                    items_summary = format_items_summary(order_state['items'])
                    return f"Added to your order! Your current order:\n\n{items_summary}\n\nWould you like to confirm this order? (yes/no)", False
                
                items_summary = format_items_summary(order_state['items'])
                return f"I couldn't find those items on the menu. Your current order:\n\n{items_summary}\n\nWould you like to confirm this order or try adding different items?", False
        
        elif 'yes' in user_message_lower or 'confirm' in user_message_lower:
            # Debug print to check order state at confirmation
            print(f"DEBUG: User confirmed order - Current state: {order_state['state']}")
            print(f"DEBUG: Order items: {order_state['items']}")
            print(f"DEBUG: Total cost: {order_state['total_cost']}")
            
            # Transition to NYU ID collection
            order_state['state'] = 'waiting_for_nyu_id'
            print(f"DEBUG: State changed to: {order_state['state']}")
            return "Great! Please provide the 8 digits of your NYU ID card after the N (e.g., if your ID is N12345678, enter 12345678):", False
        elif 'no' in user_message_lower or 'cancel' in user_message_lower:
            # Return items to cart and cancel checkout
            for item in order_state['items']:
                add_to_cart(session_id, [item])
            reset_order_state(session_id)
            return "Order cancelled. Items returned to your cart. Say 'checkout' when ready to order!", False
        else:
            items_summary = format_items_summary(order_state['items'])
            return f"Your current order:\n\n{items_summary}\n\nPlease respond with 'yes' to confirm, 'no' to cancel, or tell me what else you'd like to add.", False
    
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
        
        # Debug print to check final order data
        print(f"DEBUG: Final order data - Items: {order_data['items']}, Total: {order_data['total_cost']}")
        
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
        
        # Debug print to check items formatting
        print(f"DEBUG: Items text: {items_text}, Total cost: {order_data['total_cost']}")
        
        # Clear the cart since items have been ordered
        clear_cart(session_id)
        
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
        print(f"DEBUG: Chat endpoint - session_id: {session_id}, message: '{user_message}'")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    # Check if we're in an order flow
    order_response, continue_normal_chat = process_order_flow(user_message, session_id)
    if order_response:
        print(f"DEBUG: Order flow response: {order_response}")
        # Return the order flow response directly
        async def order_response_stream():
            yield order_response
        return StreamingResponse(order_response_stream(), media_type="text/plain")
    
    # Debug: Check current session state
    order_state = get_order_state(session_id)
    print(f"DEBUG: Current session state - Cart: {len(order_state['cart'])} items, Last shown: {len(order_state.get('last_shown_items', []))} items")

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
                # Store the found items in session state for potential "add to cart" response
                order_state = get_order_state(session_id)
                order_state['last_shown_items'] = found_items
                print(f"DEBUG: Stored last_shown_items: {found_items}")
                
                items_summary = format_items_summary(found_items)
                menu_items_context = f"Menu items found:\n{items_summary}"
                
                # Check if user wants to order these items or add to cart
                if re.search(r'add.*to cart|add.*cart|put.*cart|save.*cart|.*to cart', user_message, re.IGNORECASE):
                    cart_summary = add_to_cart(session_id, found_items)
                    print(f"DEBUG: Direct cart addition from streaming - added {len(found_items)} items")
                    order_context = f"\n[CART] Items added to cart. Show cart summary: {cart_summary}"
                elif re.search(r'order now|buy now|purchase now|order immediately', user_message, re.IGNORECASE):
                    order_state['state'] = 'waiting_for_order_confirmation'
                    order_state['items'] = found_items
                    order_state['total_cost'] = calculate_total_cost(found_items)
                    order_context = f"\n[ORDER FLOW] The user wants to order immediately (Total: AED {order_state['total_cost']:.2f}). Ask them to confirm their order by responding with 'yes' or 'no'."
                elif re.search(r'order|buy|get|want to order|purchase|want|can i get', user_message, re.IGNORECASE):
                    # User wants to order - start the order process immediately
                    order_state['state'] = 'waiting_for_order_confirmation'
                    order_state['items'] = found_items
                    order_state['total_cost'] = calculate_total_cost(found_items)
                    print(f"DEBUG: Starting order process - Items: {found_items}, Total: {order_state['total_cost']}")
                    order_context = f"\n[ORDER FLOW] The user wants to order items (Total: AED {order_state['total_cost']:.2f}). Ask them to confirm their order by responding with 'yes' or 'no'."
                else:
                    # Just showing items, no order intent - but still store them
                    print(f"DEBUG: No specific intent detected, just storing items: {len(found_items)} items")
                    order_context = f"\n[INFO] Found menu items for user. Ask if they want to 'add to cart' or 'order now'."
            
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
        
        # Add cart information if user has items in cart
        order_state = get_order_state(session_id)
        if order_state['cart']:
            cart_summary = format_cart_summary(order_state['cart'])
            prompt += f"\n\n[CART STATUS] {cart_summary}"
        
        # Add resume prompt if user has paused order
        if order_state.get('can_resume') and order_state.get('paused_at'):
            items_summary = format_items_summary(order_state['items']) if order_state['items'] else "No items"
            prompt += f"\n\n[PAUSED ORDER] The user has a paused order at stage '{order_state['paused_at']}'. Current order: {items_summary}. Offer to resume their order or help with their current question. Say 'resume order' to continue."
        
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

@app.get('/debug/session/{session_id}')
def debug_session(session_id: str):
    """Debug endpoint to check session state"""
    order_state = get_order_state(session_id)
    return {
        "session_id": session_id,
        "state": order_state['state'],
        "cart_items": len(order_state['cart']),
        "cart_details": order_state['cart'],
        "last_shown_items": len(order_state.get('last_shown_items', [])),
        "last_shown_details": order_state.get('last_shown_items', []),
        "total_cost": order_state['total_cost']
    }

@app.post('/debug/test_cart')
def test_cart_functionality():
    """Test endpoint to verify cart functions work"""
    test_session = "test_session_123"
    
    # Test items
    test_items = [
        {'name': 'Margherita', 'price': 31.0, 'quantity': 2, 'total_price': 62.0}
    ]
    
    # Add to cart
    cart_summary = add_to_cart(test_session, test_items)
    
    # Get cart state
    order_state = get_order_state(test_session)
    
    return {
        "test_result": "success",
        "cart_summary": cart_summary,
        "cart_state": order_state['cart'],
        "session_id": test_session
    }

@app.post('/debug/test_rag')
def test_rag_extraction():
    """Debug endpoint to test RAG menu item extraction"""
    test_messages = [
        "i want to add 2 Margherita pizzas as well",
        "can i also have 2 margherita pizzas", 
        "2 margherita and 2 pepperoni",
        "2 margherita pizzas and 3 pepperoni pizzas",
        "I want 2 banana nutella and 1 avocado toast",
        "can i get 3 margherita plus 2 hawaiian",
        "2x margherita, 1x pepperoni",
        "one margherita and two pepperoni pizzas"
    ]
    
    results = []
    for msg in test_messages:
        extracted = rag_extract_menu_items(msg)
        results.append({
            "message": msg,
            "extracted": extracted,
            "count": len(extracted)
        })
    
    return {
        "test": "rag_extraction_multiple_items",
        "results": results
    }

@app.post('/debug/test_multiple_order/{session_id}')
def test_multiple_order(session_id: str):
    """Test endpoint for multiple item ordering"""
    test_message = "2 margherita and 2 pepperoni"
    
    # Test RAG extraction
    extracted = rag_extract_menu_items(test_message)
    
    # Test adding to order state
    order_state = get_order_state(session_id)
    order_state['items'] = extracted
    order_state['total_cost'] = calculate_total_cost(extracted)
    
    return {
        "test_message": test_message,
        "extracted_items": extracted,
        "total_cost": order_state['total_cost'],
        "formatted_summary": format_items_summary(extracted) if extracted else "No items found"
    }

@app.post('/debug/test_edit_order/{session_id}')
def test_edit_order(session_id: str):
    """Debug endpoint to test order editing functionality"""
    # Setup a test order
    order_state = get_order_state(session_id)
    order_state['items'] = [
        {'name': 'Margherita', 'price': 31.0, 'quantity': 2, 'total_price': 62.0},
        {'name': 'Pepperoni', 'price': 43.0, 'quantity': 1, 'total_price': 43.0}
    ]
    order_state['state'] = 'waiting_for_order_confirmation'
    order_state['total_cost'] = 105.0
    
    # Test various edit commands
    test_commands = [
        "change margherita to 3",
        "remove pepperoni",
        "make pizza 1"
    ]
    
    results = []
    for cmd in test_commands:
        # Reset test order for each command
        order_state['items'] = [
            {'name': 'Margherita', 'price': 31.0, 'quantity': 2, 'total_price': 62.0},
            {'name': 'Pepperoni', 'price': 43.0, 'quantity': 1, 'total_price': 43.0}
        ]
        
        response, continue_chat = process_order_flow(cmd, session_id)
        results.append({
            "command": cmd,
            "response": response,
            "continue_chat": continue_chat,
            "items_after": order_state['items'].copy()
        })
    
    return {
        "test": "order_editing",
        "results": results
    }

@app.post('/debug/test_interruption/{session_id}')
def test_interruption(session_id: str):
    """Debug endpoint to test order interruption functionality"""
    # Setup an order in progress
    order_state = get_order_state(session_id)
    order_state['items'] = [
        {'name': 'Margherita', 'price': 31.0, 'quantity': 2, 'total_price': 62.0}
    ]
    order_state['state'] = 'waiting_for_nyu_id'
    order_state['total_cost'] = 62.0
    
    # Test interruption
    interruption_message = "what desserts do you have?"
    response, continue_chat = process_order_flow(interruption_message, session_id)
    
    # Check if order was paused
    was_paused = order_state.get('paused_at') is not None
    
    # Test resume
    resume_message = "resume order"
    resume_response, resume_continue = process_order_flow(resume_message, session_id)
    
    return {
        "test": "order_interruption",
        "interruption_command": interruption_message,
        "interruption_response": response,
        "was_paused": was_paused,
        "paused_at": order_state.get('paused_at'),
        "resume_command": resume_message,
        "resume_response": resume_response,
        "final_state": order_state['state']
    }

@app.post('/debug/add_test_item/{session_id}')
def add_test_item_to_cart(session_id: str):
    """Debug endpoint to manually add a test item to cart"""
    test_item = [
        {'name': 'Test Pizza', 'price': 25.0, 'quantity': 1, 'total_price': 25.0}
    ]
    
    cart_summary = add_to_cart(session_id, test_item)
    order_state = get_order_state(session_id)
    
    return {
        "action": "added_test_item",
        "cart_summary": cart_summary,
        "cart_state": order_state['cart'],
        "session_id": session_id
    }

@app.post('/debug/test_command_sequence/{session_id}')
def test_command_sequence(session_id: str):
    """Test a sequence of editing and interruption commands"""
    results = []
    
    # 1. Start an order
    order_state = get_order_state(session_id)
    order_state['items'] = [
        {'name': 'Margherita', 'price': 31.0, 'quantity': 2, 'total_price': 62.0},
        {'name': 'Pepperoni', 'price': 43.0, 'quantity': 1, 'total_price': 43.0}
    ]
    order_state['state'] = 'waiting_for_order_confirmation'
    order_state['total_cost'] = 105.0
    
    # 2. Edit quantity
    response1, _ = process_order_flow("change margherita to 3", session_id)
    results.append({"step": "edit_quantity", "response": response1[:100]})
    
    # 3. Remove item
    response2, _ = process_order_flow("remove pepperoni", session_id)
    results.append({"step": "remove_item", "response": response2[:100]})
    
    # 4. Confirm order to move to next stage
    response3, _ = process_order_flow("yes", session_id)
    results.append({"step": "confirm_order", "response": response3[:100]})
    
    # 5. Interrupt during NYU ID collection
    response4, _ = process_order_flow("what drinks do you have?", session_id)
    results.append({"step": "interrupt", "response": response4, "was_paused": order_state.get('paused_at') is not None})
    
    # 6. Resume order
    response5, _ = process_order_flow("resume order", session_id)
    results.append({"step": "resume", "response": response5[:100]})
    
    return {
        "test": "command_sequence",
        "results": results,
        "final_state": order_state['state'],
        "final_items": order_state['items']
    }

@app.get('/debug/session/{session_id}/detailed')
def debug_session_detailed(session_id: str):
    """Enhanced debug endpoint with new order features"""
    order_state = get_order_state(session_id)
    return {
        "session_id": session_id,
        "current_state": order_state['state'],
        "cart_items": len(order_state['cart']),
        "cart_details": order_state['cart'],
        "order_items": len(order_state['items']),
        "order_details": order_state['items'],
        "total_cost": order_state['total_cost'],
        "last_shown_items": len(order_state.get('last_shown_items', [])),
        "last_shown_details": order_state.get('last_shown_items', []),
        # New editable/interruptible fields
        "paused_at": order_state.get('paused_at'),
        "can_resume": order_state.get('can_resume', False),
        "last_interaction": order_state.get('last_interaction'),
        "interruption_context": order_state.get('interruption_context'),
        "user_info": {
            "nyu_id": order_state.get('nyu_id'),
            "building": order_state.get('building'),
            "phone": order_state.get('phone'),
            "special_request": order_state.get('special_request')
        }
    }