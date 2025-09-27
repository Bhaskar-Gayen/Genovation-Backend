from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum

class SubscriptionTier(str, Enum):
    BASIC = "BASIC"
    PRO = "PRO"

class SubscriptionBase(BaseModel):
    tier: SubscriptionTier
    stripe_subscription_id: Optional[str] = None
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None

class SubscriptionCreate(SubscriptionBase):
    user_id: UUID

class Subscription(SubscriptionBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True 