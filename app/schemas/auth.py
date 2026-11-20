from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Spaza shop or business name")
    area: str = Field(..., min_length=2, max_length=255, description="Township/suburb area e.g. Soweto")
    owner_phone: str = Field(..., min_length=10, max_length=15, description="South African phone number")
    language: str = Field("en", description="Preferred language (en, zu, xh, st)")


class BusinessUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    area: Optional[str] = Field(None, min_length=2, max_length=255)
    language: Optional[str] = None
    status: Optional[str] = None


class BusinessResponse(BaseModel):
    id: str
    name: str
    area: str
    owner_phone: str
    language: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegisterRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    area: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6, max_length=128)
    pin: Optional[str] = Field(None, pattern=r"^\d{4,6}$", description="4-6 digit numeric PIN for fast spaza login")
    language: str = Field("en")


class UserLoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=4)


class PinLoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    business_id: str
    user_id: str
    role: str
    business_name: str


class UserResponse(BaseModel):
    id: str
    business_id: str
    phone: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
