import os
import json
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI()

# Path to menu.json in the project root
MENU_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'menu.json'))

# Helper to load and flatten the menu

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
        # skip non-priced items (e.g., sauce descriptions)
    recurse(menu)
    return items

@app.get('/menu/item')
def get_menu_item(name: str = Query(..., description="Name of the menu item")):
    """
    Search for a menu item by name (case-insensitive, flattened) and return its details if found.
    """
    with open(MENU_PATH, 'r') as f:
        menu = json.load(f)
    items = flatten_menu(menu)
    for item in items:
        if item['name'].lower() == name.lower():
            return item
    return JSONResponse(status_code=404, content={"error": f"Item '{name}' not found in the menu."})

@app.get('/menu/today')
def get_menu_today():
    """
    Return the full menu as a flat list of items with name and price.
    """
    with open(MENU_PATH, 'r') as f:
        menu = json.load(f)
    return flatten_menu(menu) 