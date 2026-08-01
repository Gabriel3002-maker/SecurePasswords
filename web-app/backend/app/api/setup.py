from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from services.setup_service import run_setup

router = APIRouter(tags=["Setup"])

class SetupRequest(BaseModel):
    db_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str

@router.post("/setup")
async def run_setup_route(data: SetupRequest):
    """Ejecutar configuración inicial"""
    try:
        message = run_setup(
            db_name=data.db_name,
            admin_name=data.admin_name,
            admin_email=str(data.admin_email),
            admin_password=data.admin_password,
        )
        return {"message": message}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la configuración: {str(exc)}",
        ) from exc
