from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from typing import Optional, List, Callable
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.dependencies.auth import SECRET_KEY, ALGORITHM

async def verify_auth_token(request: Request) -> Optional[dict]:
    token = request.cookies.get("access_token")
    
    if not token:
        return None
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths: List[str] = None):
        super().__init__(app)
        self.protected_paths = protected_paths or []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check if the path requires authentication
        requires_auth = any(request.url.path.startswith(p) for p in self.protected_paths)
        
        if requires_auth:
            payload = await verify_auth_token(request)
            
            if not payload:
                if request.headers.get("accept") == "application/json":
                    raise HTTPException(
                        status_code=401,
                        detail="Not authenticated"
                    )
                return RedirectResponse(url="/auth/login")
        
        response = await call_next(request)
        return response 