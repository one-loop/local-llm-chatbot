import torch
from sentence_transformers import SentenceTransformer, util
import json
import os

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

def rag_extract_menu_item(user_message: str, threshold=0.6):
    user_embedding = model.encode(user_message, convert_to_tensor=True)
    scores = util.cos_sim(user_embedding, menu_embeddings)[0]
    best_idx = torch.argmax(scores).item()
    best_score = scores[best_idx].item()

    if best_score >= threshold:
        return flat_items[best_idx]
    return None