import sys
import os
import uvicorn

# Add backend folder to Python path so it can resolve database, forensics, etc.
sys.path.insert(0, os.path.abspath("backend"))

# Import the main FastAPI app from backend/main.py
from main import app

if __name__ == "__main__":
    # Start the server on port 8001, matching the hackathon config
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
