import os
import easyocr
import re
from flask import Flask, jsonify, request

print("Loading EasyOCR model...")
reader = easyocr.Reader(['en']) 
print("EasyOCR model loaded successfully!")

app = Flask(__name__)

def extract_float(text):
    """
    Extracts the first valid float from a string.
    Example: "P 79.27" -> 79.27
    """
    # Regex to find numbers like 79.27, 1,000.00, or 500
    # It handles optional commas and currency symbols are ignored by looking for digits
    match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', text)
    if match:
        try:
            # Remove commas for conversion (1,000.00 -> 1000.00)
            return float(match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None

def parse_receipt_data(text_lines):
    data = {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": "Unknown" # We will try to detect this
    }

    # --- 1. UNIVERSAL DATE SEARCH ---
    # Patterns: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    date_patterns = [
        r'\d{4}[-/]\d{2}[-/]\d{2}',       # 2025-11-02
        r'\d{2}[-/]\d{2}[-/]\d{4}',       # 02-11-2025
        r'\d{2}\s[A-Za-z]{3}\s\d{4}'      # 02 Nov 2025
    ]
    
    for line in text_lines:
        clean_line = line.replace(" ", "") # Remove spaces for easier matching
        for pattern in date_patterns:
            match = re.search(pattern, clean_line)
            if match:
                data["date"] = match.group(0)
                break # Stop after finding the first valid date
        if data["date"]: break

    # --- 2. SMART TOTAL HUNTING ---
    # Strategy: Look for keywords, then find the number associated with them.
    total_keywords = ["total", "amount due", "balance", "grand total", "payment"]
    potential_totals = []

    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        
        # Check if this line contains a "Total" keyword
        if any(keyword in line_lower for keyword in total_keywords):
            
            # Case A: The number is on the SAME line (e.g., "Total: 79.27")
            val = extract_float(line)
            if val: 
                potential_totals.append(val)
            
            # Case B: The number is on the NEXT line (OCR split them)
            if i + 1 < len(text_lines):
                val_next = extract_float(text_lines[i+1])
                if val_next:
                    potential_totals.append(val_next)
    
    # Decision: Usually the "Total" is the largest amount found near a keyword.
    if potential_totals:
        data["total"] = max(potential_totals)
    else:
        # Fallback: Find the largest number in the text that looks like a price (has a decimal)
        all_floats = []
        for line in text_lines:
            val = extract_float(line)
            if val and "." in line: # Ensure it has a decimal part to avoid phone numbers
                all_floats.append(val)
        if all_floats:
            data["total"] = max(all_floats)

    # --- 3. CURRENCY DETECTION ---
    # Simple check for common symbols
    full_text = " ".join(text_lines)
    if "P" in full_text and "Botswana" in full_text: data["currency"] = "BWP"
    elif "P" in full_text: data["currency"] = "P"
    elif "$" in full_text: data["currency"] = "USD"
    elif "€" in full_text: data["currency"] = "EUR"
    elif "£" in full_text: data["currency"] = "GBP"

    # --- 4. VENDOR GUESSING ---
    # The vendor is usually the first line that isn't generic noise.
    ignore_words = ["tax invoice", "receipt", "welcome", "copy", "customer"]
    
    for line in text_lines:
        # Must be at least 3 chars, mostly letters, and not in our ignore list
        if len(line) > 3 and any(c.isalpha() for c in line):
            if not any(bad_word in line.lower() for bad_word in ignore_words):
                data["vendor"] = line.title()
                break

    return data

@app.route("/process-receipt", methods=['POST'])
def process_receipt():
    if 'receipt_image' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['receipt_image']
    
    try:
        image_bytes = file.read()
        raw_result = reader.readtext(image_bytes, detail=0)
        structured_data = parse_receipt_data(raw_result)

        return jsonify({
            "status": "success",
            "data": structured_data,
            "raw_text": raw_result
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)