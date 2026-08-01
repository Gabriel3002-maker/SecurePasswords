from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
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
    folder: str = ""
    is_favorite: bool = False
    is_shared: bool = False
    tags: List[str] = []  # Nombres de etiquetas

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
    folder: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_shared: Optional[bool] = None

class CredentialResponse(CredentialBase):
    id: str
    created_by: str
    organization_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    user_permissions: Optional[dict] = None
    password_hash: Optional[str] = None  # SHA-256 para detección de duplicados
    
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

# Tag Schemas
class TagCreate(BaseModel):
    name: str
    color: str = "#6366f1"

class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    organization_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Audit Log Schemas
class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

# Password Generator Schemas
class GeneratePasswordRequest(BaseModel):
    length: int = Field(default=16, ge=6, le=128)
    uppercase: bool = True
    lowercase: bool = True
    numbers: bool = True
    symbols: bool = True

class GeneratePasswordResponse(BaseModel):
    password: str

# Change Password Schema
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

# Duplicate/Weak Password Schemas
class DuplicateGroup(BaseModel):
    password_hash: str
    count: int
    credentials: List[dict]

class WeakPasswordResponse(BaseModel):
    id: str
    host: str
    username: str
    issues: List[str]

# SSH Schemas
class SSHConnectionRequest(BaseModel):
    credential_id: str

class SSHConnectionResponse(BaseModel):
    session_id: str
    websocket_url: str
