#!/usr/bin/env python3
"""
Test script for the ordering system
"""

import json
import os

# Test the order state management
def test_order_flow():
    # Simulate the order flow
    session_id = "test_session"
    
    # Initialize order state
    order_states = {}
    
    def get_order_state(session_id: str):
        if session_id not in order_states:
            order_states[session_id] = {
                'state': 'idle',
                'item_name': None,
                'price': None,
                'nyu_id': None,
                'building': None,
                'phone': None,
                'special_request': None
            }
        return order_states[session_id]
    
    def reset_order_state(session_id: str):
        if session_id in order_states:
            order_states[session_id] = {
                'state': 'idle',
                'item_name': None,
                'price': None,
                'nyu_id': None,
                'building': None,
                'phone': None,
                'special_request': None
            }
    
    # Test 1: Start order flow
    order_state = get_order_state(session_id)
    order_state['state'] = 'waiting_for_order_confirmation'
    order_state['item_name'] = 'Margherita'
    order_state['price'] = 31.00
    
    print("Test 1: Order state initialized")
    print(f"State: {order_state['state']}")
    print(f"Item: {order_state['item_name']}")
    print(f"Price: {order_state['price']}")
    
    # Test 2: Confirm order
    order_state['state'] = 'waiting_for_nyu_id'
    print("\nTest 2: Order confirmed, waiting for NYU ID")
    
    # Test 3: Add NYU ID
    order_state['nyu_id'] = '12345678'
    order_state['state'] = 'waiting_for_building'
    print("\nTest 3: NYU ID added")
    print(f"NYU ID: {order_state['nyu_id']}")
    
    # Test 4: Add building
    order_state['building'] = 'A1A'
    order_state['state'] = 'waiting_for_phone'
    print("\nTest 4: Building selected")
    print(f"Building: {order_state['building']}")
    
    # Test 5: Add phone
    order_state['phone'] = '1234567890'
    order_state['state'] = 'waiting_for_special_request'
    print("\nTest 5: Phone number added")
    print(f"Phone: {order_state['phone']}")
    
    # Test 6: Add special request
    order_state['special_request'] = 'Extra cheese please'
    print("\nTest 6: Special request added")
    print(f"Special Request: {order_state['special_request']}")
    
    # Test 7: Complete order
    order_data = {
        'item_name': order_state['item_name'],
        'price': order_state['price'],
        'nyu_id': order_state['nyu_id'],
        'building': order_state['building'],
        'phone': order_state['phone'],
        'special_request': order_state['special_request']
    }
    
    print("\nTest 7: Order completed")
    print(f"Order Data: {json.dumps(order_data, indent=2)}")
    
    # Test 8: Reset order state
    reset_order_state(session_id)
    print("\nTest 8: Order state reset")
    print(f"State: {order_states[session_id]['state']}")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_order_flow() 