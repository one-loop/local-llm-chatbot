# validation.py - Improved Validation Functions
import re
import phonenumbers
from typing import Dict, Union, List

# Available buildings (keep this updated with your actual building list)
AVAILABLE_BUILDINGS = ["A1A", "A1B", "A1C", "A2A", "A2B", "A2C", "A3", "A4", "A5A", "A5B", "A5C", "A6A", "A6B", "A6C"]

def validate_rf_id(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid RFID Number (exactly 6 digits)"""
    if not text:
        return {
            "valid": False, 
            "message": "No RFID Number provided", 
            "rf_id": None,
            "error_type": "missing"
        }
    
    # Clean the text and find digit sequences
    cleaned_text = re.sub(r'[^\d]', ' ', str(text))
    digit_sequences = re.findall(r'\d+', cleaned_text)
    
    print(f"DEBUG: RFID validation - Input: '{text}'")
    print(f"DEBUG: Found digit sequences: {digit_sequences}")
    
    # Look for exactly 6-digit sequences
    valid_rfids = []
    for seq in digit_sequences:
        print(f"DEBUG: Checking sequence '{seq}' - length: {len(seq)}")
        if len(seq) == 6:
            valid_rfids.append(seq)
    
    if not valid_rfids:
        # Give specific feedback about what was found
        if digit_sequences:
            lengths = [len(seq) for seq in digit_sequences]
            return {
                "valid": False,
                "message": f"RFID Number must be exactly 6 digits. Found numbers with {lengths} digits.",
                "rf_id": None,
                "error_type": "invalid_format"
            }
        else:
            return {
                "valid": False,
                "message": "No numeric RFID Number found. Please provide exactly 6 digits.",
                "rf_id": None,
                "error_type": "invalid_format"
            }
    
    # Use the first valid 6-digit sequence
    rf_id = valid_rfids[0]
    print(f"DEBUG: Selected RFID: '{rf_id}' (length: {len(rf_id)})")
    
    return {
        "valid": True, 
        "message": "Valid RFID Number", 
        "rf_id": rf_id,
        "error_type": None
    }

def validate_phone_number(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid UAE phone number"""
    if not text:
        return {
            "valid": False, 
            "message": "No phone number provided", 
            "phone": None,
            "error_type": "missing"
        }
    
    # Clean the text - remove spaces, hyphens, parentheses, plus signs for extraction
    cleaned_text = re.sub(r'[\s\-\(\)\+]', '', str(text))
    
    # Find potential phone numbers (7-15 digits) - more flexible extraction
    phone_matches = re.findall(r'(\d{7,15})', cleaned_text)
    
    if not phone_matches:
        return {
            "valid": False,
            "message": "No valid phone number format found. Please provide a UAE mobile number.",
            "phone": None,
            "error_type": "invalid_format"
        }
    
    # Try to validate each potential phone number
    for phone in phone_matches:
        # Skip very short numbers
        if len(phone) < 9:
            continue
        
        # Check for UAE mobile pattern first (simpler validation)
        # UAE mobile: 10 digits starting with 05, or 9 digits starting with 5
        if len(phone) == 10 and phone.startswith('05'):
            # Check if second digit is valid UAE mobile prefix
            if phone[1:3] in ['50', '52', '54', '55', '56', '58']:
                return {
                    "valid": True,
                    "message": "Valid UAE mobile number",
                    "phone": phone,
                    "error_type": None
                }
        elif len(phone) == 9 and phone.startswith('5'):
            # Check if first two digits are valid UAE mobile prefix  
            if phone[0:2] in ['50', '52', '54', '55', '56', '58']:
                return {
                    "valid": True,
                    "message": "Valid UAE mobile number", 
                    "phone": phone,
                    "error_type": None
                }
        elif len(phone) == 12 and phone.startswith('971'):
            # UAE country code + mobile number
            mobile_part = phone[3:]
            if len(mobile_part) == 9 and mobile_part.startswith('5'):
                if mobile_part[0:2] in ['50', '52', '54', '55', '56', '58']:
                    return {
                        "valid": True,
                        "message": "Valid UAE mobile number",
                        "phone": phone,
                        "error_type": None
                    }
        
        # Fallback to phonenumbers library for complex cases
        try:
            # Try parsing with different country codes for UAE
            for country_prefix in ["AE", "UAE"]:
                try:
                    parsed = phonenumbers.parse(phone, country_prefix)
                    if phonenumbers.is_valid_number(parsed):
                        # Check if it's a UAE mobile number
                        national_number = str(parsed.national_number)
                        if (len(national_number) >= 8 and 
                            len(national_number) <= 10 and 
                            national_number.startswith('5')):
                            return {
                                "valid": True,
                                "message": "Valid UAE mobile number",
                                "phone": phone,
                                "error_type": None
                            }
                except:
                    continue
                    
            # Also try with UAE country code prefix
            if not phone.startswith('971'):
                phone_with_prefix = '971' + phone
                try:
                    parsed = phonenumbers.parse('+' + phone_with_prefix, None)
                    if phonenumbers.is_valid_number(parsed):
                        national_number = str(parsed.national_number)
                        if (len(national_number) >= 8 and 
                            len(national_number) <= 10 and 
                            national_number.startswith('5')):
                            return {
                                "valid": True,
                                "message": "Valid UAE mobile number",
                                "phone": phone,
                                "error_type": None
                            }
                except:
                    pass
                    
        except Exception as e:
            continue
    
    return {
        "valid": False,
        "message": "Invalid UAE mobile number. Please provide a valid UAE mobile number starting with '05' (e.g., 0501234567).",
        "phone": phone_matches[0] if phone_matches else None,
        "error_type": "invalid_format"
    }

def validate_building(text: str) -> Dict[str, Union[str, bool]]:
    """Validate if the text contains a valid building number"""
    if not text:
        return {
            "valid": False, 
            "message": "No building number provided", 
            "building": None,
            "error_type": "missing"
        }
    
    # Look for building pattern (case insensitive) - handle both A{digit}{A|B|C} and A{digit} patterns
    building_matches = re.findall(r'\b(A\d[ABC]|A[34])\b', str(text), re.IGNORECASE)
    
    if not building_matches:
        return {
            "valid": False,
            "message": f"Invalid building format. Must be one of: {', '.join(AVAILABLE_BUILDINGS)}",
            "building": None,
            "error_type": "invalid_format"
        }
    
    # Take the first match and normalize to uppercase
    building = building_matches[0].upper()
    
    print(f"DEBUG: Building validation - Found: '{building}', Available: {AVAILABLE_BUILDINGS}")
    print(f"DEBUG: Is '{building}' in available list: {building in AVAILABLE_BUILDINGS}")
    
    if building not in AVAILABLE_BUILDINGS:
        return {
            "valid": False,
            "message": f"Building '{building}' is not available. Valid buildings: {', '.join(AVAILABLE_BUILDINGS)}",
            "building": building,
            "error_type": "invalid_value"
        }
    
    return {
        "valid": True,
        "message": "Valid building",
        "building": building,
        "error_type": None
    }

def validate_all_credentials(rf_id_text: str = None, phone_text: str = None, 
                           building_text: str = None) -> Dict[str, any]:
    """Validate all credentials at once and return comprehensive results"""
    
    results = {
        "rf_id": validate_rf_id(rf_id_text) if rf_id_text else {"valid": False, "message": "RFID Number required", "rf_id": None, "error_type": "missing"},
        "phone": validate_phone_number(phone_text) if phone_text else {"valid": False, "message": "Phone number required", "phone": None, "error_type": "missing"},
        "building": validate_building(building_text) if building_text else {"valid": False, "message": "Building number required", "building": None, "error_type": "missing"}
    }
    
    # Overall validation status
    all_valid = all(result["valid"] for result in results.values())
    
    # Collect all errors
    errors = []
    missing_fields = []
    invalid_fields = []
    
    for field, result in results.items():
        if not result["valid"]:
            errors.append(f"{field}: {result['message']}")
            if result["error_type"] == "missing":
                missing_fields.append(field)
            else:
                invalid_fields.append(field)
    
    return {
        "all_valid": all_valid,
        "results": results,
        "errors": errors,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "extracted_values": {
            "rf_id": results["rf_id"]["rf_id"],
            "phone": results["phone"]["phone"], 
            "building": results["building"]["building"]
        }
    }

def extract_and_validate_credentials(text: str) -> Dict[str, any]:
    """Extract and validate all credentials from a single text string"""
    if not text:
        return validate_all_credentials()
    
    # First, try to extract each type of credential from the text
    rf_id_result = validate_rf_id(text)
    phone_result = validate_phone_number(text)
    building_result = validate_building(text)
    
    # Determine what was found vs what was missing
    results = {
        "rf_id": rf_id_result,
        "phone": phone_result,
        "building": building_result
    }
    
    # Calculate overall status based on what was actually found in the text
    found_items = []
    if rf_id_result["valid"]:
        found_items.append("rf_id")
    if phone_result["valid"]:
        found_items.append("phone")
    if building_result["valid"]:
        found_items.append("building")
    
    # Only report errors for items that seem to be present but invalid
    errors = []
    missing_fields = []
    invalid_fields = []
    
    # Check if text contains potential RFID (digits)
    has_digits = bool(re.search(r'\d+', text))
    # Check if text contains potential building pattern
    has_building_pattern = bool(re.search(r'\bA\d', text, re.IGNORECASE))
    # Check if text contains potential phone (longer digit sequence)
    has_long_digits = bool(re.search(r'\d{7,}', text))
    
    if has_digits and not rf_id_result["valid"]:
        invalid_fields.append("rf_id")
        errors.append(f"rf_id: {rf_id_result['message']}")
    elif not has_digits and not rf_id_result["valid"]:
        # Don't report as missing if no digits found at all
        pass
        
    if has_long_digits and not phone_result["valid"]:
        invalid_fields.append("phone")
        errors.append(f"phone: {phone_result['message']}")
    elif not has_long_digits and not phone_result["valid"]:
        # Don't report as missing if no long digit sequence found
        pass
        
    if has_building_pattern and not building_result["valid"]:
        invalid_fields.append("building")
        errors.append(f"building: {building_result['message']}")
    elif not has_building_pattern and not building_result["valid"]:
        # Don't report as missing if no building pattern found
        pass
    
    # Overall validation is successful if we found at least one valid credential
    all_valid = len(found_items) > 0 and len(invalid_fields) == 0
    
    return {
        "all_valid": all_valid,
        "results": results,
        "errors": errors,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "found_items": found_items,  # New field to show what was actually found
        "extracted_values": {
            "rf_id": rf_id_result["rf_id"] if rf_id_result["valid"] else None,
            "phone": phone_result["phone"] if phone_result["valid"] else None,
            "building": building_result["building"] if building_result["valid"] else None
        }
    }

# Updated validation tools for function calling
VALIDATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_and_validate_credentials",
            "description": "Extract and validate all credentials (RFID, phone, building) from the user's input text at once",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The user's input text containing credentials to extract and validate",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_rf_id",
            "description": "Validate if the text contains a valid RFID Number (must be exactly 6 digits)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract and validate RFID Number from",
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
            "description": "Validate if the text contains a valid UAE phone number (must start with 05 and be 10 digits total)",
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
            "description": f"Validate if the text contains a valid building number (must be one of: {', '.join(AVAILABLE_BUILDINGS)})",
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
    },
    {
        "type": "function",
        "function": {
            "name": "validate_all_credentials",
            "description": "Validate all required credentials (RFID, phone, building) at once",
            "parameters": {
                "type": "object",
                "properties": {
                    "rf_id_text": {
                        "type": "string",
                        "description": "Text containing RFID Number",
                    },
                    "phone_text": {
                        "type": "string", 
                        "description": "Text containing phone number",
                    },
                    "building_text": {
                        "type": "string",
                        "description": "Text containing building number",
                    }
                },
                "required": [],
            },
        },
    }
]

# Function mapping for execution
VALIDATION_FUNCTIONS = {
    'validate_rf_id': validate_rf_id,
    'validate_phone_number': validate_phone_number,
    'validate_building': validate_building,
    'validate_all_credentials': validate_all_credentials,
    'extract_and_validate_credentials': extract_and_validate_credentials
}