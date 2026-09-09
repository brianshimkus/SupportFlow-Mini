from typing import Literal

from pydantic import BaseModel, Field

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
