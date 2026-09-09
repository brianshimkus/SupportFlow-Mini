import os
import sqlite3
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title='SupportFlow Mini')

DB_PATH = Path(os.getenv('SUPPORTFLOW_DB_PATH', 'supportflow.db'))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_tier TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            ai_category TEXT NOT NULL,
            ai_priority TEXT NOT NULL,
            ai_team TEXT NOT NULL,
            ai_summary TEXT NOT NULL,
            ai_suggested_response TEXT NOT NULL,
            ai_confidence REAL NOT NULL,
            status TEXT NOT NULL,
            approved INTEGER,
            final_category TEXT,
            final_priority TEXT,
            final_team TEXT,
            final_response TEXT,
            reviewer_note TEXT,
            delivery_status TEXT,
            delivery_detail TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            detail TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );
        """
    )
    conn.commit()
    conn.close()


init_db()

Category = Literal['billing', 'technical', 'account', 'feature_request', 'other']
Priority = Literal['low', 'medium', 'high', 'urgent']
Team = Literal['billing', 'support', 'engineering', 'customer_success']


class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=80)
    customer_tier: Literal['standard', 'premium', 'enterprise']
    subject: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=12, max_length=4000)


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    team: Team
    summary: str
    suggested_response: str
    confidence: float = Field(ge=0, le=1)


class TicketReview(BaseModel):
    approved: bool
    final_category: Category | None = None
    final_priority: Priority | None = None
    final_team: Team | None = None
    final_response: str | None = None
    reviewer_note: str | None = None


def mock_triage(ticket: TicketCreate) -> TriageResult:
    text = f'{ticket.subject} {ticket.description}'.lower()
    if 'invoice' in text or 'charged' in text:
        category, team = 'billing', 'billing'
    elif 'api' in text or 'error' in text:
        category, team = 'technical', 'engineering'
    else:
        category, team = 'other', 'support'
    priority = 'high' if 'blocked' in text or 'error' in text else 'low'
    return TriageResult(
        category=category,
        priority=priority,
        team=team,
        summary=ticket.description[:180],
        suggested_response='Thanks. The assigned team will review this request.',
        confidence=0.80,
    )


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'ai_mode': os.getenv('AI_MODE', 'mock'),
    }
