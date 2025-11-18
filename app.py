import os
import pytesseract
from PIL import Image
import io
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

# --- CONFIGURATION ---
# Windows Path: Verify this matches your actual installation!
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_receipt_data(text):
    data = {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": "Unknown"
    }

    # 1. DATE HUNTING
    # Looks for YYYY-MM-DD, DD-MM-YYYY, or DD MMM YYYY
    date_patterns = [
        r'\d{4}[-/]\d{2}[-/]\d{2}',
        r'\d{2}[-/]\d{2}[-/]\d{4}',
        r'\d{2}\s[A-Za-z]{3}\s\d{4}'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data["date"] = match.group(0)
            break

    # 2. SMART TOTAL HUNTING
    # Looks for decimal numbers like 79.27
    price_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
    prices = re.findall(price_pattern, text)
    valid_prices = []
    for p in prices:
        try:
            # Clean up string (remove commas) and convert to float
            valid_prices.append(float(p.replace(',', '')))
        except:
            continue
            
    if valid_prices:
        data["total"] = max(valid_prices)

    # 3. CURRENCY & VENDOR
    if "P" in text: data["currency"] = "P"
    
    for line in text.split('\n'):
        clean = line.strip()
        if len(clean) > 3 and "invoice" not in clean.lower():
            data["vendor"] = clean
            break

    return data

@app.route("/")
def home():
    return jsonify({"status": "online", "engine": "Tesseract OCR"}), 200

@app.route("/process-receipt", methods=['POST'])
def process_receipt():
    if 'receipt_image' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['receipt_image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # --- FIX: Load image safely into memory first ---
        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # --- FIX: Convert to RGB to prevent alpha channel issues ---
        image = image.convert('RGB')
        
        print(f"Processing file: {file.filename}...") # Debug print
        
        # Perform OCR
        raw_text = pytesseract.image_to_string(image)
        
        print(f"Raw Text Found: {raw_text[:50]}...") # Debug print
        
        # Parse Data
        structured_data = parse_receipt_data(raw_text)

        return jsonify({
            "status": "success",
            "data": structured_data,
            "raw_text_lines": raw_text.split('\n')
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)