from sqlalchemy import Boolean, Column, String, Integer, ForeignKey, DateTime, Enum as SQLEnum, Table, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

# Tabla pivote para relación muchos a muchos entre credenciales y etiquetas
credential_tags = Table(
    'credential_tags', Base.metadata,
    Column('credential_id', String, ForeignKey('credentials.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', String, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    organization_id = Column(String, ForeignKey("organizations.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="users", foreign_keys=[organization_id])
    credentials = relationship("Credential", back_populates="created_by_user", foreign_keys="Credential.created_by")
    permissions = relationship("CredentialPermission", back_populates="user", foreign_keys="CredentialPermission.user_id")
    audit_logs = relationship("AuditLog", back_populates="user")

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="organization", foreign_keys="User.organization_id")
    credentials = relationship("Credential", back_populates="organization")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    color = Column(String, default="#6366f1")
    organization_id = Column(String, ForeignKey("organizations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization")
    credentials = relationship("Credential", secondary=credential_tags, back_populates="tags_rel")


class Credential(Base):
    __tablename__ = "credentials"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    host = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password_encrypted = Column(String, nullable=False)
    token_encrypted = Column(String)
    password_hash = Column(String)  # SHA-256 para detectar duplicados
    port = Column(Integer)
    comment = Column(String)
    created_by = Column(String, ForeignKey("users.id"))
    organization_id = Column(String, ForeignKey("organizations.id"))
    folder = Column(String, default="", index=True)
    is_favorite = Column(Boolean, default=False)
    is_shared = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User", back_populates="credentials", foreign_keys=[created_by])
    organization = relationship("Organization", back_populates="credentials")
    permissions = relationship("CredentialPermission", back_populates="credential", cascade="all, delete-orphan")
    tags_rel = relationship("Tag", secondary=credential_tags, back_populates="credentials")

class CredentialPermission(Base):
    __tablename__ = "credential_permissions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    credential_id = Column(String, ForeignKey("credentials.id", ondelete="CASCADE"))
    user_id = Column(String, ForeignKey("users.id"))
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_connect_ssh = Column(Boolean, default=True)
    granted_by = Column(String, ForeignKey("users.id"))
    granted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    credential = relationship("Credential", back_populates="permissions")
    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id = Column(String)
    details = Column(String)  # JSON string
    ip_address = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")

class SSHSession(Base):
    __tablename__ = "ssh_sessions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    credential_id = Column(String, ForeignKey("credentials.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id = Column(String, primary_key=True, default=generate_uuid)
    purpose = Column(String, default="master_password")
    code_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
