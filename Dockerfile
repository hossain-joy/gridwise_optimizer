FROM python:3.11-slim

WORKDIR /app

# Install CBC solver (required by PuLP)
RUN apt-get update && apt-get install -y coinor-cbc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Port is expected to be passed via ENV $PORT
ENV PORT=8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
