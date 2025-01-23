from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List

router = APIRouter()

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user."""
    # This is a dummy implementation. Replace with actual user creation logic
    return {
        "id": 1,
        "email": user.email,
        "username": user.username,
        "is_active": True
    }

@router.get("/", response_model=List[User])
async def read_users(skip: int = 0, limit: int = 100):
    """Get list of users."""
    # This is a dummy implementation. Replace with actual user retrieval logic
    return [
        {
            "id": 1,
            "email": "test@example.com",
            "username": "test_user",
            "is_active": True
        }
    ]

@router.get("/{user_id}", response_model=User)
async def read_user(user_id: int):
    """Get user by ID."""
    # This is a dummy implementation. Replace with actual user retrieval logic
    return {
        "id": user_id,
        "email": "test@example.com",
        "username": "test_user",
        "is_active": True
    } 