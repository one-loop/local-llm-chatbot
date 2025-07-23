import os
import json
import re
import datetime
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from menu_embeddings import rag_extract_menu_items

# Paths for conversation and order files
CONVERSATIONS_DIR = os.path.join(os.path.dirname(__file__), 'conversations')
TEMP_ORDERS_DIR = os.path.join(os.path.dirname(__file__), 'temp_orders')

# Ensure directories exist
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
os.makedirs(TEMP_ORDERS_DIR, exist_ok=True)

class ConversationLogger:
    """Handles logging and managing conversation files"""
    
    @staticmethod
    def get_conversation_file(session_id: str) -> str:
        """Get the conversation file path for a session"""
        return os.path.join(CONVERSATIONS_DIR, f"conversation_{session_id}.json")
    
    @staticmethod
    def get_order_file(session_id: str) -> str:
        """Get the order file path for a session"""
        return os.path.join(TEMP_ORDERS_DIR, f"order_{session_id}.json")
    
    @staticmethod
    def log_message(session_id: str, message: str, sender: str = "user"):
        """Log a message to the conversation file"""
        conversation_file = ConversationLogger.get_conversation_file(session_id)
        
        message_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "sender": sender,
            "message": message
        }
        
        # Load existing conversation or create new
        conversation = []
        if os.path.exists(conversation_file):
            try:
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
            except:
                conversation = []
        
        # Add new message
        conversation.append(message_data)
        
        # Save back to file
        with open(conversation_file, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
        
        print(f"DEBUG: Logged message for session {session_id}: {message[:50]}...")
    
    @staticmethod
    def get_conversation(session_id: str) -> List[Dict]:
        """Get the entire conversation for a session"""
        conversation_file = ConversationLogger.get_conversation_file(session_id)
        
        if os.path.exists(conversation_file):
            try:
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    @staticmethod
    def cleanup_session(session_id: str):
        """Clean up conversation and order files for a session"""
        conversation_file = ConversationLogger.get_conversation_file(session_id)
        order_file = ConversationLogger.get_order_file(session_id)
        
        for file_path in [conversation_file, order_file]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"DEBUG: Cleaned up file: {file_path}")
                except Exception as e:
                    print(f"ERROR: Could not remove {file_path}: {e}")

class OrderKeywordDetector:
    """Background task for detecting order keywords in conversations"""
    
    # Keywords that indicate order intent
    ORDER_KEYWORDS = [
        r'\border\b', r'\bbuy\b', r'\bget\b', r'\bwant\b', r'\bpurchase\b',
        r'\bi\'?ll have\b', r'\bcan i get\b', r'\bcan i have\b',
        r'\badd.*cart\b', r'\bcheckout\b', r'\bplace.*order\b'
    ]
    
    # Keywords for order confirmation/details
    CONFIRMATION_KEYWORDS = [
        r'\byes\b', r'\bconfirm\b', r'\bokay\b', r'\bsure\b', r'\bgood\b'
    ]
    
    @staticmethod
    def scan_for_order_intent(conversation: List[Dict]) -> Optional[Dict]:
        """Scan conversation for order-related patterns"""
        
        # Get recent messages (last 10)
        recent_messages = conversation[-10:] if len(conversation) > 10 else conversation
        user_messages = [msg for msg in recent_messages if msg['sender'] == 'user']
        
        if not user_messages:
            return None
        
        # Combine recent user messages for analysis
        combined_text = " ".join([msg['message'] for msg in user_messages])
        
        print(f"DEBUG: Scanning combined text: {combined_text[:100]}...")
        
        # Check for order keywords
        has_order_intent = any(
            re.search(keyword, combined_text, re.IGNORECASE) 
            for keyword in OrderKeywordDetector.ORDER_KEYWORDS
        )
        
        if not has_order_intent:
            return None
        
        # Extract items from the conversation
        extracted_items = rag_extract_menu_items(combined_text)
        
        if not extracted_items:
            print("DEBUG: Order intent detected but no items found")
            return None
        
        # Analyze conversation stage
        stage = OrderKeywordDetector._determine_order_stage(user_messages)
        
        order_data = {
            "items": extracted_items,
            "stage": stage,
            "total_cost": sum(item.get('total_price', 0) for item in extracted_items),
            "detected_at": datetime.datetime.now().isoformat(),
            "conversation_length": len(conversation)
        }
        
        print(f"DEBUG: Order detected - Items: {len(extracted_items)}, Stage: {stage}")
        print(f"DEBUG: Last user message: '{user_messages[-1]['message'] if user_messages else 'None'}'")
        return order_data
    
    @staticmethod
    def _determine_order_stage(user_messages: List[Dict]) -> str:
        """Determine what stage of the order process we're in"""
        
        # Look at the last few messages to determine stage
        recent_text = " ".join([msg['message'] for msg in user_messages[-5:]])
        
        # Check for confirmation words first (most recent priority)
        last_message = user_messages[-1]['message'].lower().strip() if user_messages else ""
        
        # If last message is confirmation, mark as confirming
        if re.search(r'\b(yes|yeah|yep|confirm|ok|okay|sure|correct|right|proceed)\b', last_message):
            return "confirming_order"
        
        # Check for NYU ID patterns (8 digits)
        if re.search(r'\b\d{8}\b', recent_text):
            return "nyu_id_provided"
        
        # Check for building patterns
        if re.search(r'\bA\d[ABC]\b', recent_text, re.IGNORECASE):
            return "building_provided"
        
        # Check for phone patterns (9-15 digits in a row)
        phone_text = recent_text.replace(' ', '').replace('-', '').replace('+', '')
        if re.search(r'\b\d{9,15}\b', phone_text):
            return "phone_provided"
        
        return "order_intent"
    
    @staticmethod
    def save_detected_order(session_id: str, order_data: Dict):
        """Save detected order data to temporary file"""
        order_file = ConversationLogger.get_order_file(session_id)
        
        with open(order_file, 'w', encoding='utf-8') as f:
            json.dump(order_data, f, indent=2, ensure_ascii=False)
        
        print(f"DEBUG: Saved order data for session {session_id}")
    
    @staticmethod
    def get_detected_order(session_id: str) -> Optional[Dict]:
        """Get detected order data if it exists"""
        order_file = ConversationLogger.get_order_file(session_id)
        
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

class BackgroundOrderProcessor:
    """Background task processor for order detection"""
    
    @staticmethod
    async def process_session_orders(session_id: str):
        """Background task to process orders for a session"""
        
        # Get the conversation
        conversation = ConversationLogger.get_conversation(session_id)
        
        if len(conversation) < 2:  # Need at least some conversation
            return
        
        # Scan for order intent
        order_data = OrderKeywordDetector.scan_for_order_intent(conversation)
        
        if order_data:
            # Check if we already have an order for this session
            existing_order = OrderKeywordDetector.get_detected_order(session_id)
            
            # Only update if this is new or significantly different
            if not existing_order or BackgroundOrderProcessor._is_order_updated(existing_order, order_data):
                OrderKeywordDetector.save_detected_order(session_id, order_data)
                print(f"DEBUG: Updated order for session {session_id}")
    
    @staticmethod
    def _is_order_updated(old_order: Dict, new_order: Dict) -> bool:
        """Check if the order has been meaningfully updated"""
        
        # Always update if no old order
        if not old_order:
            return True
        
        # Check if items changed
        old_items = old_order.get('items', [])
        new_items = new_order.get('items', [])
        
        if len(old_items) != len(new_items):
            return True
        
        # Check if stage progressed
        old_stage = old_order.get('stage', '')
        new_stage = new_order.get('stage', '')
        
        # Always update if stage changed
        if old_stage != new_stage:
            return True
        
        # Update if conversation progressed significantly
        old_conv_length = old_order.get('conversation_length', 0)
        new_conv_length = new_order.get('conversation_length', 0)
        
        # Update if conversation has grown by 2+ messages
        if new_conv_length - old_conv_length >= 2:
            return True
        
        return False

def test_order_detection():
    """Test the order detection system"""
    
    test_session = "test_session_456"
    
    # Simulate a conversation
    test_conversation = [
        {"timestamp": "2025-01-01T10:00:00", "sender": "user", "message": "hello"},
        {"timestamp": "2025-01-01T10:00:10", "sender": "bot", "message": "Hi! How can I help you?"},
        {"timestamp": "2025-01-01T10:00:20", "sender": "user", "message": "do you have pizza?"},
        {"timestamp": "2025-01-01T10:00:30", "sender": "bot", "message": "Yes, we have margherita for AED 31"},
        {"timestamp": "2025-01-01T10:00:40", "sender": "user", "message": "I want 2 margherita pizzas"},
        {"timestamp": "2025-01-01T10:00:50", "sender": "bot", "message": "Great choice!"},
        {"timestamp": "2025-01-01T10:01:00", "sender": "user", "message": "yes, confirm my order"},
        {"timestamp": "2025-01-01T10:01:10", "sender": "user", "message": "my nyu id is 12345678"}
    ]
    
    # Save test conversation
    conversation_file = ConversationLogger.get_conversation_file(test_session)
    with open(conversation_file, 'w', encoding='utf-8') as f:
        json.dump(test_conversation, f)
    
    # Test order detection
    detected_order = OrderKeywordDetector.scan_for_order_intent(test_conversation)
    
    print("Test Order Detection Results:")
    print(f"Detected order: {detected_order}")
    
    if detected_order:
        OrderKeywordDetector.save_detected_order(test_session, detected_order)
    
    # Cleanup
    ConversationLogger.cleanup_session(test_session)
    
    return detected_order is not None

if __name__ == "__main__":
    # Run test
    success = test_order_detection()
    print(f"Test {'PASSED' if success else 'FAILED'}")