from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.schemas.user import TokenData

# JWT Bearer token scheme
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def get_current_user_mobile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user's mobile number from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception

        mobile_number: str = payload.get("sub")
        if mobile_number is None:
            raise credentials_exception

        token_data = TokenData(mobile_number=mobile_number)
    except JWTError:
        raise credentials_exception

    return token_data.mobile_number


def get_current_user(mobile_number: str = Depends(get_current_user_mobile), db: Session = Depends(get_db)):
    """Get current user from database using mobile number from JWT"""
    from services.user_service import UserService

    user = UserService.get_user_by_mobile_number(db, mobile_number=mobile_number)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user_from_token(token: str, db: Session):
    """
    Get current user from database using token string directly
    This function is used by middleware and other components that have direct access to token
    """
    try:
        # Verify the token and get payload
        payload = verify_token(token)
        if payload is None:
            return None

        # Extract mobile number from token payload
        mobile_number: str = payload.get("sub")
        if mobile_number is None:
            return None

        # Get user from database using mobile number
        from services.user_service import UserService
        user = UserService.get_user_by_mobile_number(db, mobile_number=mobile_number)

        return user

    except Exception as e:
        # Log the error but don't raise exception (middleware should handle gracefully)
        import logging
        logger = logging.getLogger("auth_utils")
        logger.warning(f"Failed to get user from token: {e}")
        return None


def get_mobile_from_token(token: str) -> Optional[str]:
    """
    Extract mobile number from token without database lookup
    Useful for quick token validation
    """
    try:
        payload = verify_token(token)
        if payload is None:
            return None

        mobile_number: str = payload.get("sub")
        return mobile_number

    except Exception:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without raising exception
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        exp = payload.get("exp")
        if exp is None:
            return True

        # Check if token is expired
        exp_datetime = datetime.fromtimestamp(exp)
        return exp_datetime < datetime.now()

    except JWTError:
        return True


def get_token_payload(token: str) -> Optional[dict]:
    """
    Get full token payload without database lookup
    Useful for extracting additional token data
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def validate_token_format(auth_header: str) -> Optional[str]:
    """
    Validate Authorization header format and extract token
    Returns token string if valid, None if invalid
    """
    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ")[1]
        return token if token else None
    except IndexError:
        return None