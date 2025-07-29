"""
Test script for validation module
Run this to verify all validation functions work correctly
"""

from validation import (
    validate_rf_id,
    validate_phone_number, 
    validate_building,
    validate_all_credentials,
    extract_and_validate_credentials
)

def test_rf_id_validation():
    """Test RFID validation"""
    print("=== Testing RFID Validation ===")
    
    test_cases = [
        ("123456", True, "Valid 6-digit RFID"),
        ("12345", False, "Too short"),
        ("1234567", False, "Too long"),
        ("abc123", False, "Contains letters"),
        ("", False, "Empty input"),
        ("My RFID is 987654", True, "RFID in sentence"),
        ("123 456", False, "With space"),
        ("RF123456ID", True, "RFID with text around")
    ]
    
    for text, expected_valid, description in test_cases:
        result = validate_rf_id(text)
        status = "✅" if result["valid"] == expected_valid else "❌"
        print(f"{status} {description}: '{text}' -> {result['valid']} ({result['message']})")
        if result["valid"]:
            print(f"   Extracted RFID: {result['rf_id']}")
    print()

def test_phone_validation():
    """Test phone number validation"""
    print("=== Testing Phone Validation ===")
    
    test_cases = [
        ("0501234567", True, "Valid UAE mobile"),
        ("971501234567", True, "With country code"),
        ("050 123 4567", True, "With spaces"),
        ("050-123-4567", True, "With hyphens"),
        ("+971501234567", True, "With + prefix"),
        ("0401234567", False, "Invalid prefix (04)"),
        ("12345", False, "Too short"),
        ("", False, "Empty input"),
        ("Call me at 0551234567", True, "Phone in sentence"),
        ("My number is +971 55 123 4567", True, "Complex format")
    ]
    
    for text, expected_valid, description in test_cases:
        result = validate_phone_number(text)
        status = "✅" if result["valid"] == expected_valid else "❌"
        print(f"{status} {description}: '{text}' -> {result['valid']} ({result['message']})")
        if result["valid"]:
            print(f"   Extracted phone: {result['phone']}")
    print()

def test_building_validation():
    """Test building validation"""
    print("=== Testing Building Validation ===")
    
    test_cases = [
        ("A1A", True, "Valid building"),
        ("a1a", True, "Lowercase valid building"),
        ("A2B", True, "Another valid building"),
        ("A7A", False, "Invalid building (A7 doesn't exist)"),
        ("B1A", False, "Wrong letter prefix"),
        ("A11", False, "Wrong format"),
        ("", False, "Empty input"),
        ("I'm in building A3", True, "Building in sentence"),
        ("Building: A5C", True, "With label")
    ]
    
    for text, expected_valid, description in test_cases:
        result = validate_building(text)
        status = "✅" if result["valid"] == expected_valid else "❌"
        print(f"{status} {description}: '{text}' -> {result['valid']} ({result['message']})")
        if result["valid"]:
            print(f"   Extracted building: {result['building']}")
    print()

def test_comprehensive_validation():
    """Test comprehensive validation"""
    print("=== Testing Comprehensive Validation ===")
    
    # Test case 1: All valid
    text1 = "My RFID is 123456, I'm in building A1A, call me at 0501234567"
    result1 = extract_and_validate_credentials(text1)
    
    print("Test 1 - All valid credentials:")
    print(f"All valid: {result1['all_valid']}")
    print(f"Extracted values: {result1['extracted_values']}")
    print(f"Errors: {result1['errors']}")
    print()
    
    # Test case 2: Mixed valid/invalid
    text2 = "RFID 12345, building X1A, phone 123"
    result2 = extract_and_validate_credentials(text2)
    
    print("Test 2 - Mixed valid/invalid:")
    print(f"All valid: {result2['all_valid']}")
    print(f"Missing fields: {result2['missing_fields']}")
    print(f"Invalid fields: {result2['invalid_fields']}")
    print(f"Errors: {result2['errors']}")
    print()
    
    # Test case 3: Empty input
    result3 = extract_and_validate_credentials("")
    
    print("Test 3 - Empty input:")
    print(f"All valid: {result3['all_valid']}")
    print(f"Missing fields: {result3['missing_fields']}")
    print()

def run_all_tests():
    """Run all validation tests"""
    print("🧪 Running Validation Tests\n")
    
    test_rf_id_validation()
    test_phone_validation()
    test_building_validation()
    test_comprehensive_validation()
    
    print("✅ All tests completed!")

if __name__ == "__main__":
    run_all_tests()