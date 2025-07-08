import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from datetime import datetime

# -- DATABASE SETUP --

# Use DATABASE_URL env or fallback to SQLite in container root for dev.
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./notes.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Dependency for DB session management
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -- SCHEMAS --

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128, description="Title of the note")
    content: str = Field("", description="Content of the note")

class NoteUpdate(BaseModel):
    title: str = Field(None, min_length=1, max_length=128, description="(Optional) New title of the note")
    content: str = Field(None, description="(Optional) New content of the note")

class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# -- FASTAPI APP SETUP & METADATA --

app = FastAPI(
    title="Notes API",
    description="REST API to manage notes: create, read, update, delete.",
    version="1.0.0",
    openapi_tags=[
        {"name": "notes", "description": "Operations with notes (CRUD)"},
        {"name": "health", "description": "Health check endpoint"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev; restrict in production as appropriate
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- ENDPOINTS --

# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check")
def health_check():
    """Simple health check endpoint to verify server is running."""
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.post("/notes/", response_model=NoteOut, status_code=201, tags=["notes"], summary="Create a new note")
def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    """Create a new note.
    Args:
        note: NoteCreate schema with title and content.
    Returns:
        The created note with assigned id and timestamps.
    """
    db_note = Note(title=note.title, content=note.content, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

# PUBLIC_INTERFACE
@app.get("/notes/", response_model=List[NoteOut], tags=["notes"], summary="List all notes")
def list_notes(db: Session = Depends(get_db)):
    """Retrieve a list of all notes ordered by creation (newest first).
    Returns:
        List of notes.
    """
    notes = db.query(Note).order_by(Note.created_at.desc()).all()
    return notes

# PUBLIC_INTERFACE
@app.get("/notes/{note_id}/", response_model=NoteOut, tags=["notes"], summary="Get a specific note by ID")
def get_note(note_id: int, db: Session = Depends(get_db)):
    """Get a specific note by its ID.
    Args:
        note_id: ID of the note to retrieve.
    Returns:
        The specified note.
    """
    db_note = db.query(Note).filter(Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    return db_note

# PUBLIC_INTERFACE
@app.put("/notes/{note_id}/", response_model=NoteOut, tags=["notes"], summary="Update a note")
def update_note(note_id: int, note: NoteUpdate, db: Session = Depends(get_db)):
    """Update the title and/or content for a specific note.
    Args:
        note_id: ID of the note to update.
        note: NoteUpdate schema with optional title/content.
    Returns:
        The updated note.
    """
    db_note = db.query(Note).filter(Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.title is not None:
        db_note.title = note.title
    if note.content is not None:
        db_note.content = note.content
    db_note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_note)
    return db_note

# PUBLIC_INTERFACE
@app.delete("/notes/{note_id}/", status_code=status.HTTP_204_NO_CONTENT, tags=["notes"], summary="Delete a note")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    """Delete a note by its ID.
    Args:
        note_id: ID of the note to delete.
    Returns:
        204 No Content on success.
    """
    db_note = db.query(Note).filter(Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(db_note)
    db.commit()
    return None

# Note: Run with `uvicorn src.api.main:app --reload` from the notes_backend root.
