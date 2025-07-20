#!/usr/bin/env python3
"""
Test script for the complete ordering flow
"""

import requests
import json
import time

def test_order_flow():
    """Test the complete ordering flow"""
    
    # Test data
    session_id = "test_session_123"
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Complete Order Flow")
    print("=" * 50)
    
    # Step 1: Ask about a menu item
    print("\n1. Asking about menu item...")
    response1 = requests.post(f"{base_url}/chat", json={
        "message": "Is Margherita available?",
        "history": [],
        "session_id": session_id
    })
    
    if response1.status_code == 200:
        print("✅ Step 1: Menu item inquiry successful")
        print(f"Response: {response1.text[:200]}...")
    else:
        print(f"❌ Step 1 failed: {response1.status_code}")
        return
    
    # Step 2: Confirm order
    print("\n2. Confirming order...")
    response2 = requests.post(f"{base_url}/chat", json={
        "message": "Yes, I want to order it",
        "history": [],
        "session_id": session_id
    })
    
    if response2.status_code == 200:
        print("✅ Step 2: Order confirmation successful")
        print(f"Response: {response2.text[:200]}...")
    else:
        print(f"❌ Step 2 failed: {response2.status_code}")
        return
    
    # Step 3: Provide NYU ID
    print("\n3. Providing NYU ID...")
    response3 = requests.post(f"{base_url}/chat", json={
        "message": "12345678",
        "history": [],
        "session_id": session_id
    })
    
    if response3.status_code == 200:
        print("✅ Step 3: NYU ID provided successfully")
        print(f"Response: {response3.text[:200]}...")
    else:
        print(f"❌ Step 3 failed: {response3.status_code}")
        return
    
    # Step 4: Select building
    print("\n4. Selecting building...")
    response4 = requests.post(f"{base_url}/chat", json={
        "message": "A1A",
        "history": [],
        "session_id": session_id
    })
    
    if response4.status_code == 200:
        print("✅ Step 4: Building selected successfully")
        print(f"Response: {response4.text[:200]}...")
    else:
        print(f"❌ Step 4 failed: {response4.status_code}")
        return
    
    # Step 5: Provide phone number
    print("\n5. Providing phone number...")
    response5 = requests.post(f"{base_url}/chat", json={
        "message": "1234567890",
        "history": [],
        "session_id": session_id
    })
    
    if response5.status_code == 200:
        print("✅ Step 5: Phone number provided successfully")
        print(f"Response: {response5.text[:200]}...")
    else:
        print(f"❌ Step 5 failed: {response5.status_code}")
        return
    
    # Step 6: Provide special request
    print("\n6. Providing special request...")
    response6 = requests.post(f"{base_url}/chat", json={
        "message": "Extra cheese please",
        "history": [],
        "session_id": session_id
    })
    
    if response6.status_code == 200:
        print("✅ Step 6: Special request provided successfully")
        print(f"Response: {response6.text[:200]}...")
    else:
        print(f"❌ Step 6 failed: {response6.status_code}")
        return
    
    print("\n🎉 All steps completed successfully!")
    print("Check orders.txt file for the saved order.")

if __name__ == "__main__":
    try:
        test_order_flow()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend server. Make sure it's running on port 5000.")
    except Exception as e:
        print(f"❌ Error: {e}") 