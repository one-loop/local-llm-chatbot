#!/usr/bin/env python3
"""
Test script for the improved item extraction function
"""

import re

def extract_menu_item(user_message: str):
    # Common category words to remove from the end of item names
    category_words = [
        'pizza', 'wings', 'bowl', 'sandwich', 'wrap', 'salad', 'soup', 'burger',
        'fries', 'chips', 'drink', 'beverage', 'coffee', 'tea', 'juice', 'soda',
        'ice cream', 'dessert', 'cake', 'cookie', 'bread', 'roll', 'bun'
    ]
    
    patterns = [
        r'is ([\w\s]+) available',
        r'do you have ([\w\s]+)',
        r'price of ([\w\s]+)',
        r'how much is the ([\w\s]+)',
        r'how much are the ([\w\s]+)',
        r'how much is ([\w\s]+)',
        r'can I get ([\w\s]+)',
        r'can I have ([\w\s]+)',
        r'can I have the ([\w\s]+)',
        r'can I have a ([\w\s]+)',
        r'have a ([\w\s]+)',
        r'have the ([\w\s]+)',
        r'order the ([\w\s]+)',
        r'order a ([\w\s]+)',
        r'order ([\w\s]+)',
        r'get ([\w\s]+)',
        r'want ([\w\s]+)',
        r'like ([\w\s]+)',
    ]
    
    for pat in patterns:
        m = re.search(pat, user_message, re.IGNORECASE)
        if m:
            extracted_item = m.group(1).strip()
            
            # Remove category words from the end of the item name
            item_lower = extracted_item.lower()
            for category in category_words:
                # Check if the item ends with the category word
                if item_lower.endswith(f' {category}'):
                    # Remove the category word and any leading/trailing spaces
                    extracted_item = extracted_item[:-len(category)].strip()
                    break
                elif item_lower == category:
                    # If the entire item is just a category word, return it as is
                    return extracted_item
            
            return extracted_item
    return None

def test_extraction():
    """Test the item extraction function with various inputs"""
    
    test_cases = [
        # Pizza tests
        ("Can I order a pepperoni pizza", "pepperoni"),
        ("Is pepperoni pizza available", "pepperoni"),
        ("Do you have margherita pizza", "margherita"),
        ("Order the beef supreme pizza", "beef supreme"),
        
        # Wings tests
        ("I want chicken wings", "chicken"),
        ("Order chicken wings", "chicken"),
        ("Get some wings", "wings"),
        
        # Bowl tests
        ("Can I get a berry bowl", "berry"),
        ("Order the tropical bowl", "tropical"),
        ("I want an acai bowl", "acai"),
        
        # Other items
        ("Order chicken nuggets", "chicken nuggets"),
        ("Get mozzarella sticks", "mozzarella sticks"),
        ("I want halloumi", "halloumi"),
        
        # Items without category words
        ("Order salmon", "salmon"),
        ("Get beef steak", "beef steak"),
        ("I want tofu", "tofu"),
        
        # Edge cases
        ("Order pizza", "pizza"),  # Should return as is if it's just "pizza"
        ("Get wings", "wings"),    # Should return as is if it's just "wings"
        ("I want soup", "soup"),   # Should return as is if it's just "soup"
    ]
    
    print("🧪 Testing Item Extraction")
    print("=" * 50)
    
    all_passed = True
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = extract_menu_item(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{i:2d}. {status} Input: '{input_text}'")
        print(f"    Expected: '{expected}' | Got: '{result}'")
        if result != expected:
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return all_passed

if __name__ == "__main__":
    test_extraction() 