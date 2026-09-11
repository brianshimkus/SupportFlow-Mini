import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title='SupportFlow Mini')

DB_PATH = Path(os.getenv('SUPPORTFLOW_DB_PATH', 'supportflow.db'))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


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


@app.post('/api/tickets', status_code=201)
def create_ticket(ticket: TicketCreate):
    result = mock_triage(ticket)
    now = utc_now()
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO tickets (
            created_at, customer_name, customer_tier, subject, description,
            ai_category, ai_priority, ai_team, ai_summary, ai_suggested_response,
            ai_confidence, status, delivery_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            ticket.customer_name,
            ticket.customer_tier,
            ticket.subject,
            ticket.description,
            result.category,
            result.priority,
            result.team,
            result.summary,
            result.suggested_response,
            result.confidence,
            'awaiting_review',
            'not_configured',
        ),
    )
    ticket_id = cur.lastrowid
    conn.execute(
        """
        INSERT INTO events (ticket_id, event_type, created_at, detail)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_id, 'triaged', now, result.model_dump_json()),
    )
    conn.commit()
    row = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


@app.get('/api/tickets')
def list_tickets():
    conn = get_db()
    rows = conn.execute('SELECT * FROM tickets ORDER BY id DESC').fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


@app.post('/api/tickets/{ticket_id}/review')
def review_ticket(ticket_id: int, review: TicketReview):
    conn = get_db()
    row = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail='Ticket not found')
    if row['status'] != 'awaiting_review':
        conn.close()
        raise HTTPException(status_code=409, detail='Ticket already reviewed')
    final_category = review.final_category or row['ai_category']
    final_priority = review.final_priority or row['ai_priority']
    final_team = review.final_team or row['ai_team']
    final_response = review.final_response or row['ai_suggested_response']
    now = utc_now()
    conn.execute(
        """
        UPDATE tickets SET
            status = ?,
            approved = ?,
            final_category = ?,
            final_priority = ?,
            final_team = ?,
            final_response = ?,
            reviewer_note = ?,
            delivery_status = ?
        WHERE id = ?
        """,
        (
            'reviewed',
            1 if review.approved else 0,
            final_category,
            final_priority,
            final_team,
            final_response,
            review.reviewer_note,
            'not_configured',
            ticket_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO events (ticket_id, event_type, created_at, detail)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_id, 'reviewed', now, review.model_dump_json()),
    )
    conn.commit()
    updated = conn.execute(
        'SELECT * FROM tickets WHERE id = ?', (ticket_id,)
    ).fetchone()
    conn.close()
    return row_to_dict(updated)


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'ai_mode': os.getenv('AI_MODE', 'mock'),
    }


@app.get('/api/metrics')
def metrics():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) AS n FROM tickets').fetchone()['n']
    reviewed = conn.execute(
        "SELECT COUNT(*) AS n FROM tickets WHERE status = 'reviewed'"
    ).fetchone()['n']
    approved_unchanged = conn.execute(
        """
        SELECT COUNT(*) AS n FROM tickets
        WHERE status = 'reviewed'
          AND approved = 1
          AND final_category = ai_category
          AND final_priority = ai_priority
          AND final_team = ai_team
          AND final_response = ai_suggested_response
        """
    ).fetchone()['n']
    avg_row = conn.execute(
        """
        SELECT AVG(ai_confidence) AS avg_confidence
        FROM tickets
        WHERE status = 'reviewed'
        """
    ).fetchone()
    conn.close()
    agreement_rate = (approved_unchanged / reviewed) if reviewed else None
    return {
        'total_tickets': total,
        'reviewed': reviewed,
        'approved_unchanged': approved_unchanged,
        'agreement_rate': agreement_rate,
        'avg_confidence': avg_row['avg_confidence'],
    }
