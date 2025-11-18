import os
import pytesseract
from PIL import Image
import re
from flask import Flask, jsonify, request
import io

app = Flask(__name__)

# --- CONFIGURATION (Tesseract Path & Settings) ---

# 1. PATH FIX (For local Windows development only)
# If we are on Windows ('nt'), we MUST tell Python where Tesseract is installed.
# On the Cloud (Linux/posix), it skips this and finds tesseract automatically.
if os.name == 'nt':
    # This path MUST match your Windows installation of tesseract.exe
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 2. TESSERACT STABILITY FIX (PSM mode that stops crashing on containers)
# PSM 6 is Page Segmentation Mode: Assume a single uniform block of text (stable for receipts).
CUSTOM_TESSERACT_CONFIG = r'--psm 6'

def parse_receipt_data(text):
    """Parses raw text output from Tesseract to extract structured data."""
    data = {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": "Unknown"
    }

    # --- 1. DATE HUNTING ---
    # Checks for YYYY-MM-DD or DD-MM-YYYY formats.
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

    # --- 2. SMART TOTAL HUNTING (Largest decimal number) ---
    # Looks for numbers like 79.27 or 1,000.00
    price_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
    prices = re.findall(price_pattern, text)
    
    valid_prices = []
    for p in prices:
        try:
            valid_prices.append(float(p.replace(',', '')))
        except:
            continue
            
    if valid_prices:
        data["total"] = max(valid_prices)

    # --- 3. CURRENCY & VENDOR ---
    if "P" in text: data["currency"] = "P"
    
    # Guess vendor: First non-generic line of text.
    for line in text.split('\n'):
        clean = line.strip()
        if len(clean) > 3 and "invoice" not in clean.lower():
            data["vendor"] = clean
            break

    return data

@app.route("/")
def home():
    """Health check route."""
    return jsonify({"status": "online", "engine": "Tesseract OCR"}), 200

@app.route("/process-receipt", methods=['POST'])
def process_receipt():
    # --- Input Validation ---
    if 'receipt_image' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['receipt_image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # --- Robust Image Loading ---
        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # --- Image Preprocessing ---
        image = image.convert('RGB')
        
        # --- OCR Execution ---
        raw_text = pytesseract.image_to_string(image, config=CUSTOM_TESSERACT_CONFIG)
        
        # --- Data Parsing ---
        structured_data = parse_receipt_data(raw_text)

        # --- Final Output ---
        return jsonify({
            "status": "success",
            "data": structured_data,
            "raw_text_lines": raw_text.split('\n')
        }), 200

    except Exception as e:
        # This is where the crash happens. Return a general error to the client.
        print(f"CRITICAL ERROR during OCR processing: {e}")
        return jsonify({"error": "Internal Server Error during OCR processing. Please contact support."}), 500

if __name__ == '__main__':
    # This runs the app locally. On Render, Gunicorn runs the app.
    app.run(debug=True)