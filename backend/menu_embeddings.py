import torch
from sentence_transformers import SentenceTransformer, util
import json
import os
import re
from typing import List, Dict, Optional

# Load and flatten menu
def flatten_menu(menu):
    items = []
    def recurse(obj, parent_name=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, float, int, str)):
                    recurse(v, k)
                else:
                    recurse(v, parent_name)
        elif isinstance(obj, (float, int)):
            items.append({'name': parent_name, 'price': obj})
    recurse(menu)
    return items

# Load menu.json
MENU_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'menu.json'))
with open(MENU_PATH, 'r') as f:
    menu = json.load(f)

flat_items = flatten_menu(menu)
item_names = [item["name"] for item in flat_items]

# Load model and encode
model = SentenceTransformer("all-MiniLM-L6-v2")
menu_embeddings = model.encode(item_names, convert_to_tensor=True)

def extract_quantities_and_items(user_message: str) -> List[Dict[str, str]]:
    """
    Extract items with quantities from user message.
    Returns list of dicts with 'text' and 'quantity' keys.
    """
    # Convert number words to digits
    number_words = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'a': '1', 'an': '1'
    }
    
    # Replace number words with digits
    processed_message = user_message.lower()
    for word, digit in number_words.items():
        processed_message = re.sub(r'\b' + word + r'\b', digit, processed_message)
    
    # Patterns to match quantity + item combinations
    patterns = [
        r'(\d+)\s*x?\s*([^,\n\r]+?)(?=\s*(?:,|and|\d+\s*x?|\n|\r|$))',  # "2x pizza", "3 burgers"
        r'(\d+)\s+([^,\n\r]+?)(?=\s*(?:,|and|\d+\s*|\n|\r|$))',        # "2 pizza"
        r'([^,\n\r]+?)\s*x\s*(\d+)(?=\s*(?:,|and|\n|\r|$))',           # "pizza x 2"
    ]
    
    items_with_qty = []
    processed_spans = []
    
    print(f"DEBUG: Processing message: '{user_message}' -> '{processed_message}'")
    
    for pattern in patterns:
        for match in re.finditer(pattern, processed_message, re.IGNORECASE):
            start, end = match.span()
            
            # Check if this span overlaps with already processed spans
            if any(start < p_end and end > p_start for p_start, p_end in processed_spans):
                continue
                
            processed_spans.append((start, end))
            
            groups = match.groups()
            if groups[0].isdigit():
                qty, item_text = groups[0], groups[1].strip()
            else:
                item_text, qty = groups[0].strip(), groups[1]
            
            print(f"DEBUG: Found pattern match - qty: {qty}, item: {item_text}")
            
            items_with_qty.append({
                'text': item_text,
                'quantity': int(qty)
            })
    
    # If no quantity patterns found, look for items without explicit quantities
    if not items_with_qty:
        # Split by common separators and look for menu items
        parts = re.split(r',|\sand\s|\n|\r', processed_message, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            if len(part) > 2:  # Ignore very short parts
                items_with_qty.append({
                    'text': part,
                    'quantity': 1
                })
    
    print(f"DEBUG: Final extracted items: {items_with_qty}")
    return items_with_qty

def rag_extract_menu_items(user_message: str, threshold=0.5) -> List[Dict]:
    """
    Extract multiple menu items from user message using RAG.
    Returns list of items with their quantities.
    """
    # Extract items with quantities from the message
    items_with_qty = extract_quantities_and_items(user_message)
    
    found_items = []
    
    print(f"DEBUG: RAG processing {len(items_with_qty)} extracted items")
    
    for item_data in items_with_qty:
        item_text = item_data['text']
        quantity = item_data['quantity']
        
        print(f"DEBUG: RAG processing item: '{item_text}' with quantity: {quantity}")
        
        # Use RAG to find the best matching menu item
        user_embedding = model.encode(item_text, convert_to_tensor=True)
        scores = util.cos_sim(user_embedding, menu_embeddings)[0]
        best_idx = torch.argmax(scores).item()
        best_score = scores[best_idx].item()
        
        print(f"DEBUG: Best match for '{item_text}': '{item_names[best_idx]}' (score: {best_score})")
        
        if best_score >= threshold:
            menu_item = flat_items[best_idx].copy()
            menu_item['quantity'] = quantity
            menu_item['total_price'] = menu_item['price'] * quantity
            print(f"DEBUG: Added item: {menu_item}")
            found_items.append(menu_item)
    
    print(f"DEBUG: RAG final result: {found_items}")
    return found_items

def rag_extract_menu_item(user_message: str, threshold=0.6) -> Optional[Dict]:
    """
    Original single-item extraction function for backwards compatibility.
    """
    items = rag_extract_menu_items(user_message, threshold)
    return items[0] if items else None

# Helper function to format multiple items for display
def format_items_summary(items: List[Dict]) -> str:
    """Format multiple items into a readable summary."""
    if not items:
        return ""
    
    item_lines = []
    total_cost = 0
    
    for item in items:
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        total_price = item.get('total_price', price * qty)
        total_cost += total_price
        
        if qty > 1:
            item_lines.append(f"{qty}x {item['name']} (AED {price} each = AED {total_price})")
        else:
            item_lines.append(f"{item['name']} (AED {price})")
    
    summary = "\n".join(item_lines)
    if len(items) > 1:
        summary += f"\n\nTotal: AED {total_cost:.2f}"
    
    return summary