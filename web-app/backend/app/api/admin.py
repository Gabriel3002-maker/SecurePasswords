from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.models import User, UserRole
from schemas.schemas import UserCreate, UserResponse, UserUpdate
from api.deps import get_current_admin
from core.security import get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Listar todos los usuarios de la organización (solo admin)"""
    users = db.query(User).filter(
        User.organization_id == current_user.organization_id
    ).all()
    
    return users

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Crear nuevo usuario en la organización (solo admin)"""
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya está registrado"
        )
    
    # Crear usuario en la misma organización que el admin
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role or UserRole.USER,
        organization_id=current_user.organization_id,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Actualizar usuario (solo admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Verificar que el usuario pertenece a la misma organización
    if user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar este usuario"
        )
    
    update_data = user_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Desactivar usuario (soft delete)"""
    if user_id == str(current_admin.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta"
        )
        
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == current_admin.organization_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    user.is_active = False
    db.commit()

@router.get("/export")
def export_credentials(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Exportar todas las credenciales a Excel"""
    try:
        import pandas as pd
        from io import BytesIO
        from core.encryption import decrypt_password
        from models.models import Credential
        
        # Obtener todas las credenciales de la organización
        credentials = db.query(Credential).filter(
            Credential.organization_id == current_admin.organization_id
        ).all()
        
        data = []
        for cred in credentials:
            try:
                password = decrypt_password(cred.password_encrypted)
            except Exception:
                password = "[Error desencriptando]"
                
            data.append({
                "Host": cred.host,
                "Usuario": cred.username,
                "Contraseña": password,
                "Puerto": cred.port,
                "Comentario": cred.comment,
                "Creado por": cred.created_by
            })
            
        df = pd.DataFrame(data)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Credenciales')
            
        output.seek(0)
        
        headers = {
            'Content-Disposition': 'attachment; filename="credenciales_export.xlsx"'
        }
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            headers=headers,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Librerías de exportación no instaladas (pandas, openpyxl)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al exportar: {str(e)}"
        )

@router.post("/import")
async def import_credentials(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Importar credenciales desde Excel"""
    try:
        import pandas as pd
        from core.encryption import encrypt_password
        from models.models import Credential
        
        # Leer archivo
        contents = await file.read()
        df = pd.read_excel(contents)
        
        # Validar columnas requeridas
        required_columns = ["Host", "Usuario", "Contraseña"]
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo debe contener las columnas: {', '.join(required_columns)}"
            )
            
        count = 0
        for _, row in df.iterrows():
            # Verificar duplicados (Host + Usuario + Puerto)
            port = int(row.get("Puerto", 22)) if pd.notna(row.get("Puerto")) else 22
            
            exists = db.query(Credential).filter(
                Credential.organization_id == current_admin.organization_id,
                Credential.host == str(row["Host"]),
                Credential.username == str(row["Usuario"]),
                Credential.port == port
            ).first()
            
            if exists:
                continue
                
            # Crear credencial
            cred = Credential(
                host=str(row["Host"]),
                username=str(row["Usuario"]),
                password_encrypted=encrypt_password(str(row["Contraseña"])),
                port=port,
                comment=str(row.get("Comentario", "")) if pd.notna(row.get("Comentario")) else None,
                created_by=current_admin.id,
                organization_id=current_admin.organization_id
            )
            db.add(cred)
            count += 1
            
        db.commit()
        return {"message": f"Se importaron {count} credenciales exitosamente"}
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Librerías de importación no instaladas"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al importar: {str(e)}"
        )
