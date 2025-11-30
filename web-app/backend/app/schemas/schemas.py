from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str
    organization_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None

class UserResponse(UserBase):
    id: str
    organization_id: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Credential Schemas
class CredentialBase(BaseModel):
    host: str
    username: str
    port: Optional[int] = None
    comment: Optional[str] = None
    is_shared: bool = False

class CredentialCreate(CredentialBase):
    password: str
    token: Optional[str] = None

class CredentialUpdate(BaseModel):
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    port: Optional[int] = None
    comment: Optional[str] = None
    is_shared: Optional[bool] = None

class CredentialResponse(CredentialBase):
    id: str
    created_by: str
    organization_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    user_permissions: Optional[dict] = None  # Permisos del usuario actual
    # No incluimos password por seguridad
    
    class Config:
        from_attributes = True

class CredentialWithPassword(CredentialResponse):
    """Solo para cuando el usuario tiene permiso de ver la contraseña"""
    password: str
    token: Optional[str] = None

# Permission Schemas
class PermissionCreate(BaseModel):
    user_id: str
    can_view: bool = True
    can_edit: bool = False
    can_delete: bool = False
    can_connect_ssh: bool = True

class PermissionResponse(BaseModel):
    id: str
    credential_id: str
    user_id: str
    can_view: bool
    can_edit: bool
    can_delete: bool
    can_connect_ssh: bool
    granted_at: datetime
    
    class Config:
        from_attributes = True

# Organization Schemas
class OrganizationCreate(BaseModel):
    name: str

class OrganizationResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# SSH Schemas
class SSHConnectionRequest(BaseModel):
    credential_id: str

class SSHConnectionResponse(BaseModel):
    session_id: str
    websocket_url: str
