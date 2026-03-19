"""
Authentication & Authorization module for AI-RAG Engine.
JWT RS256 auth with RBAC roles, bcrypt passwords, Redis session cache, TOTP MFA.
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, timedelta, timezone
import uuid
import os
import re
import logging

import jwt  # PyJWT
import bcrypt

# Optional TOTP support
try:
    import pyotp
except ImportError:
    pyotp = None

from core.redis_client import cache_session, get_session, revoke_session
from core.db import get_sync_session, is_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# JWT configuration — RS256 when keys are present, HS256 dev fallback
# ---------------------------------------------------------------------------
_JWT_PRIVATE_KEY: str | None = os.getenv("JWT_PRIVATE_KEY")  # PEM string
_JWT_PUBLIC_KEY: str | None = os.getenv("JWT_PUBLIC_KEY")     # PEM string
_JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")

if _JWT_PRIVATE_KEY and _JWT_PUBLIC_KEY:
    JWT_ALGORITHM = "RS256"
    _SIGN_KEY = _JWT_PRIVATE_KEY
    _VERIFY_KEY = _JWT_PUBLIC_KEY
    logger.info("Auth using RS256 (asymmetric keys)")
else:
    JWT_ALGORITHM = "HS256"
    _SIGN_KEY = _JWT_SECRET
    _VERIFY_KEY = _JWT_SECRET
    logger.warning("Auth using HS256 dev fallback — set JWT_PRIVATE_KEY / JWT_PUBLIC_KEY for production")

JWT_ACCESS_EXPIRY_MIN = int(os.getenv("JWT_ACCESS_EXPIRY_MIN", "15"))
JWT_REFRESH_EXPIRY_MIN = int(os.getenv("JWT_REFRESH_EXPIRY_MIN", str(7 * 24 * 60)))  # 7 days

BCRYPT_COST = 12  # work factor
VALID_ROLES = {"viewer", "editor", "admin", "system"}

# Cookie settings for refresh token
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_SECURE = os.getenv("ENVIRONMENT", "development") == "production"
REFRESH_COOKIE_SAMESITE = "lax"

# In-memory fallback (used when PostgreSQL is unavailable)
_inmemory_users: dict = {}
_inmemory_revoked: set = set()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "editor"

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: dict


class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_token(user_id: str, email: str, role: str, minutes: int, token_type: str = "access") -> tuple[str, str]:
    """Return (encoded_jwt, jti)."""
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "jti": jti,
        "type": token_type,
        "iat": _now_utc(),
        "exp": _now_utc() + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, _SIGN_KEY, algorithm=JWT_ALGORITHM), jti


async def decode_token(token: str) -> dict:
    """Decode, verify signature, check revocation in Redis then in-memory."""
    try:
        payload = jwt.decode(token, _VERIFY_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti", "")
    # Check Redis revocation first
    session = await get_session(jti)
    if session is None:
        # Redis miss — might not be cached or Redis is down; check in-memory
        if jti in _inmemory_revoked:
            raise HTTPException(status_code=401, detail="Token revoked")
    # If session is stored in Redis and explicitly empty → revoked (shouldn't happen, we delete)
    return payload


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Extract & validate current user from JWT."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await decode_token(credentials.credentials)
    return {
        "id": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
        "jti": payload.get("jti"),
    }


def require_role(*roles: str):
    """Dependency factory: require specific RBAC role(s)."""
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Required role: {', '.join(roles)}")
        return user
    return checker


# ---------------------------------------------------------------------------
# DB helpers — try PostgreSQL, fall back to in-memory
# ---------------------------------------------------------------------------
def _get_user_by_email(email: str) -> dict | None:
    """Lookup user.  Uses sync SQLAlchemy when PG available."""
    if is_async_db():
        # For now we use sync session inside endpoints (cheap for auth)
        from core.models import User
        with get_sync_session() as session:
            user = session.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
            if user:
                return {
                    "id": user.id, "email": user.email,
                    "password_hash": user.password_hash, "role": user.role,
                    "mfa_enabled": user.mfa_enabled, "mfa_secret": user.mfa_secret,
                    "created_at": str(user.created_at), "last_login": str(user.last_login) if user.last_login else None,
                }
        return None
    return _inmemory_users.get(email)


def _create_user(user_id: str, email: str, pw_hash: str, role: str) -> dict:
    user_dict = {
        "id": user_id, "email": email, "password_hash": pw_hash,
        "role": role, "mfa_enabled": False, "mfa_secret": None,
        "created_at": _now_utc().isoformat(), "last_login": _now_utc().isoformat(),
    }
    if is_async_db():
        from core.models import User
        with get_sync_session() as session:
            session.add(User(id=user_id, email=email, password_hash=pw_hash, role=role))
            session.commit()
    else:
        _inmemory_users[email] = user_dict
    return user_dict


def _update_last_login(email: str) -> None:
    if is_async_db():
        from core.models import User
        with get_sync_session() as session:
            user = session.query(User).filter(User.email == email).first()
            if user:
                user.last_login = _now_utc()
                session.commit()
    else:
        u = _inmemory_users.get(email)
        if u:
            u["last_login"] = _now_utc().isoformat()


# Seed a default admin for dev mode
_default_admin_email = "admin@ai-rag.local"
if not is_async_db():
    _inmemory_users[_default_admin_email] = {
        "id": str(uuid.uuid4()),
        "email": _default_admin_email,
        "password_hash": hash_password("Admin1234"),
        "role": "admin",
        "mfa_enabled": False,
        "mfa_secret": None,
        "created_at": _now_utc().isoformat(),
        "last_login": None,
    }


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set refresh token as HttpOnly, Secure, SameSite cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        max_age=JWT_REFRESH_EXPIRY_MIN * 60,
        path="/auth",  # Only sent to auth endpoints
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def _get_refresh_token_from_request(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """Extract refresh token from cookie first, then Authorization header."""
    # Try cookie first
    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    # Fallback to Authorization header (for backwards compatibility)
    if credentials:
        return credentials.credentials
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(req: RegisterRequest, response: Response):
    """Register a new user account [public]. Sets refresh token as HttpOnly cookie."""
    if _get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    role = req.role if req.role in ("viewer", "editor") else "editor"
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)
    user_dict = _create_user(user_id, req.email, pw_hash, role)

    access, a_jti = create_token(user_id, req.email, role, JWT_ACCESS_EXPIRY_MIN, "access")
    refresh, _ = create_token(user_id, req.email, role, JWT_REFRESH_EXPIRY_MIN, "refresh")
    await cache_session(a_jti, user_id, role, ttl=JWT_ACCESS_EXPIRY_MIN * 60)

    _set_refresh_cookie(response, refresh)
    safe = {k: v for k, v in user_dict.items() if k not in ("password_hash", "mfa_secret")}
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=JWT_ACCESS_EXPIRY_MIN * 60, user=safe)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response):
    """Authenticate user and return JWT token pair. Sets refresh token as HttpOnly cookie."""
    user = _get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _update_last_login(req.email)

    access, a_jti = create_token(user["id"], user["email"], user["role"], JWT_ACCESS_EXPIRY_MIN, "access")
    refresh, _ = create_token(user["id"], user["email"], user["role"], JWT_REFRESH_EXPIRY_MIN, "refresh")
    await cache_session(a_jti, user["id"], user["role"], ttl=JWT_ACCESS_EXPIRY_MIN * 60)

    _set_refresh_cookie(response, refresh)
    safe = {k: v for k, v in user.items() if k not in ("password_hash", "mfa_secret")}
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=JWT_ACCESS_EXPIRY_MIN * 60, user=safe)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Exchange a refresh token for a new access token. Reads from HttpOnly cookie or header."""
    token = _get_refresh_token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated — no refresh token")
    payload = await decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Not a refresh token")

    access, a_jti = create_token(payload["sub"], payload["email"], payload["role"], JWT_ACCESS_EXPIRY_MIN, "access")
    # Issue new refresh token (rotation)
    new_refresh, _ = create_token(payload["sub"], payload["email"], payload["role"], JWT_REFRESH_EXPIRY_MIN, "refresh")
    await cache_session(a_jti, payload["sub"], payload["role"], ttl=JWT_ACCESS_EXPIRY_MIN * 60)

    _set_refresh_cookie(response, new_refresh)
    user = _get_user_by_email(payload["email"]) or {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
    safe = {k: v for k, v in user.items() if k not in ("password_hash", "mfa_secret")}
    return TokenResponse(access_token=access, refresh_token=new_refresh, expires_in=JWT_ACCESS_EXPIRY_MIN * 60, user=safe)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Revoke JWT token via Redis + in-memory set. Clears refresh cookie."""
    _clear_refresh_cookie(response)
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, _VERIFY_KEY, algorithms=[JWT_ALGORITHM])
            jti = payload.get("jti", "")
            await revoke_session(jti)
            _inmemory_revoked.add(jti)
        except Exception:
            pass
    return None


# ---- MFA ----
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(user: dict = Depends(get_current_user)):
    """Generate TOTP secret and provisioning URI."""
    if pyotp is None:
        raise HTTPException(status_code=501, detail="pyotp not installed — MFA unavailable")
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="AI-RAG-Engine")
    # Persist secret to user record
    if is_async_db():
        from core.models import User
        with get_sync_session() as session:
            u = session.query(User).filter(User.id == user["id"]).first()
            if u:
                u.mfa_secret = secret
                session.commit()
    else:
        u = _inmemory_users.get(user["email"])
        if u:
            u["mfa_secret"] = secret
    return MFASetupResponse(secret=secret, qr_uri=uri)


@router.post("/mfa/verify")
async def mfa_verify(code: str, user: dict = Depends(get_current_user)):
    """Verify TOTP code and enable MFA on first successful verify."""
    if pyotp is None:
        raise HTTPException(status_code=501, detail="pyotp not installed")
    db_user = _get_user_by_email(user["email"])
    secret = db_user.get("mfa_secret") if db_user else None
    if not secret:
        raise HTTPException(status_code=400, detail="MFA not set up — call /auth/mfa/setup first")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    # Mark MFA enabled
    if is_async_db():
        from core.models import User
        with get_sync_session() as session:
            u = session.query(User).filter(User.id == user["id"]).first()
            if u:
                u.mfa_enabled = True
                session.commit()
    else:
        u = _inmemory_users.get(user["email"])
        if u:
            u["mfa_enabled"] = True
    return {"verified": True, "mfa_enabled": True}
