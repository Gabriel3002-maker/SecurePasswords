from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse
from services.setup_service import run_setup

router = APIRouter(tags=["Setup"])

class SetupRequest(BaseModel):
    db_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    language: str | None = None
    master_password: str | None = None
    telegram_bot_token: str | None = None

@router.post("/setup")
async def run_setup_route(request: Request, data: SetupRequest):
    """Ejecutar configuración inicial"""
    try:
        message = run_setup(
            db_name=data.db_name,
            admin_name=data.admin_name,
            admin_email=str(data.admin_email),
            admin_password=data.admin_password,
            language=data.language,
            master_password=data.master_password,
            telegram_bot_token=data.telegram_bot_token,
        )
        response = {"message": message}
        if data.telegram_bot_token:
            from core import telegram as telegram_service
            telegram_service.start_polling()
        if data.language:
            response_headers = {"set-cookie": f"app_lang={data.language}; Path=/; HttpOnly=False; SameSite=Lax"}
            return JSONResponse(content=response, headers=response_headers)
        return response
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
