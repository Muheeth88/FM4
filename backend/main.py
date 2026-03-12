from dotenv import load_dotenv
import os

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
from database.db import init_db
from routes.repository import router as repository_router
from routes.analyzer import router as analyzer_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

app = FastAPI(title="QE Framework Migration System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routes
app.include_router(repository_router)
app.include_router(analyzer_router)

@app.get("/")
async def root():
    return {"message": "QE Framework Migration System API is running"}


