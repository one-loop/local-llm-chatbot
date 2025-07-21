# Ordering System Documentation

## Overview
The ordering system allows users to place orders for menu items through the chatbot. The system guides users through a step-by-step process to collect all necessary information.

## Order Flow

### 1. Menu Item Inquiry
- User asks about a specific menu item (e.g., "Is Margherita available?" or "What's the price of Margherita?")
- Bot responds with item availability and price
- Bot asks if user wants to place an order

### 2. Order Confirmation
- User confirms they want to order the item
- Bot asks for confirmation: "Would you like to place an order for this item?"

### 3. NYU ID Collection
- User provides the 8 digits of their NYU ID (e.g., if ID is N12345678, enter 12345678)
- System validates the format (must be exactly 8 digits)

### 4. Building Selection
- User selects from available buildings:
  - A1A, A1B, A1C, A2A, A2B, A2C, A3, A4, A5A, A5B, A5C, A6A, A6B, A6C

### 5. Phone Number
- User provides their phone number
- System validates phone number format

### 6. Special Requests
- User can provide special requests (e.g., "Extra cheese", "No onions")
- If no special requests, user can say "no" or "none"

### 7. Order Confirmation
- System displays final order confirmation with all details
- Order is saved to `orders.txt` file

## Order Storage
All orders are stored in `orders.txt` with the following format:
```
=== ORDER - 2024-01-15 14:30:25 ===
Item: Margherita
Price: AED 31.0
NYU ID: N12345678
Building: A1A
Phone: 1234567890
Special Request: Extra cheese please
==================================================
```

## Technical Implementation

### State Management
- Uses in-memory session-based state management
- Each user session maintains order state
- States: `idle`, `waiting_for_order_confirmation`, `waiting_for_nyu_id`, `waiting_for_building`, `waiting_for_phone`, `waiting_for_special_request`

### Validation
- NYU ID: Must be exactly 8 digits
- Building: Must be from the predefined list
- Phone: Basic validation for 10-15 digits

### Error Handling
- Invalid inputs prompt user to re-enter information
- Order can be cancelled at any time
- System gracefully handles missing or invalid data

## API Endpoints

### POST /chat
- Handles all chat interactions including ordering
- Accepts: `message`, `history`, `session_id`
- Returns: Streaming response with bot replies

## Testing
Run the test script to verify the ordering system:
```bash
python3 test_ordering.py
```

## Usage Example
1. User: "Is Margherita pizza available?"
2. Bot: "Yes! Margherita is available for AED 31.00. Would you like to place an order?"
3. User: "Yes"
4. Bot: "Please provide the 8 digits of your NYU ID..."
5. User: "12345678"
6. Bot: "Please select your building from: A1A, A1B, A1C..."
7. User: "A1A"
8. Bot: "Please provide your phone number:"
9. User: "1234567890"
10. Bot: "Do you have any special requests?"
11. User: "Extra cheese please"
12. Bot: "Order confirmed for: 1x Margherita. NYU ID: N12345678, Building: A1A, Phone Number: 1234567890. Special Request: Extra cheese please." 