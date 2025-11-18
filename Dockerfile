# Use Python 3.11 (Slim version to save space)
FROM python:3.11-slim

# 1. Install Tesseract and system tools
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev && \
    apt-get clean

# 2. Setup the App Directory
WORKDIR /app
COPY . /app

# 3. Install Python Libraries
RUN pip install --no-cache-dir -r requirements.txt

# 4. Run the Server
# Render automatically sets the PORT to 10000, so we bind to it
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]