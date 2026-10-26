
import logging

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_db, Base, engine
from backend import models

# Configure logging so database errors appear in the terminal.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VakeelAI API",
    description="Court case scraper and legal draft generator",
    version="1.0.0",
)

# Create tables for the SQLAlchemy models that have been imported.
# This creates missing tables; it does not migrate existing schemas.
Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "Welcome to VakeelAI API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    try:
        # Run a real query to verify the database connection.
        db.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "mysql",
        }

    except SQLAlchemyError:
        # Print the detailed exception in the terminal for debugging.
        logger.exception("Database connection failed")

        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Check the server logs.",
        )
