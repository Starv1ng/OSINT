# services/api/app/api/auth.py
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/token", auto_error=False)

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    # OSINT: bypass simple de token para desarrollo
    # Aceptar cualquier token o ausencia de token en modo desarrollo
    if token is None or token == "" or token == "testtoken":
        return {"username": "dev", "role": "admin"}
    if token:
        return {"username": "dev", "role": "admin"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido"
    )