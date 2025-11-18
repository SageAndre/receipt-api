import os
import pytesseract
from PIL import Image
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

# --- CONFIGURATION ---
# If we are on Windows (your PC), tell Python where Tesseract is installed.
# If we are on the Cloud (Linux), it finds it automatically.
if os.name == 'nt':
    # This assumes you installed Tesseract to the default location
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_receipt_data(text):
    data = {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": "Unknown"
    }

    # 1. DATE HUNTING (Standard formats)
    date_patterns = [
        r'\d{4}[-/]\d{2}[-/]\d{2}',       # 2025-11-02
        r'\d{2}[-/]\d{2}[-/]\d{4}',       # 02-11-2025
        r'\d{2}\s[A-Za-z]{3}\s\d{4}'      # 02 Nov 2025
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data["date"] = match.group(0)
            break

    # 2. SMART TOTAL HUNTING (Largest number with a decimal)
    # Looks for numbers like 79.27 or 1,000.00
    price_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
    prices = re.findall(price_pattern, text)
    
    valid_prices = []
    for p in prices:
        try:
            # Remove commas to convert to float
            valid_prices.append(float(p.replace(',', '')))
        except:
            continue
            
    if valid_prices:
        data["total"] = max(valid_prices)

    # 3. CURRENCY & VENDOR
    if "P" in text: data["currency"] = "P"
    
    # Vendor guess: First line that is longer than 3 chars and isn't "Receipt"
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
        # Open image with Pillow
        image = Image.open(file.stream)
        
        # The Magic: Tesseract extracts text
        raw_text = pytesseract.image_to_string(image)
        
        # Parse it
        structured_data = parse_receipt_data(raw_text)

        return jsonify({
            "status": "success",
            "data": structured_data,
            "raw_text_lines": raw_text.split('\n')
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)