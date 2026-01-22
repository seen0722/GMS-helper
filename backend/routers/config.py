from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc
from typing import List, Optional
from pydantic import BaseModel

from backend.database.database import get_db
from backend.database import models

router = APIRouter(
    tags=["config"],
    responses={404: {"description": "Not found"}},
)

class TestSuiteSchema(BaseModel):
    id: int
    name: str
    display_name: str
    is_required: bool
    match_rule: str
    sort_order: int
    description: Optional[str] = None

    class Config:
        orm_mode = True

@router.get("/suites", response_model=List[TestSuiteSchema])
async def get_test_suites(db: Session = Depends(get_db)):
    """
    Get all configured test suites, sorted by sort_order.
    Used by frontend to render matrix and backend to validate compliance.
    """
    suites = db.query(models.TestSuiteConfig).order_by(asc(models.TestSuiteConfig.sort_order)).all()
    # Convert integer boolean (0/1) to boolean if needed, but Pydantic handles int->bool coercion usually.
    # However, let's ensure it maps correctly if we use Integer in DB.
    # Pydantic v1/v2 coerce 1 to True.
    return suites
