import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
import hashlib
import bcrypt
from db.postgresql import fetchrow, execute

router = APIRouter()

# Security Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False
    # To support backward compatibility with plain text passwords during transition
    if not hashed_password.startswith("$2b$") and not hashed_password.startswith("$2a$"): 
        return plain_password == hashed_password
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    if not password:
        return None
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        dealer_id: str = payload.get("dealer_id")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = await fetchrow("SELECT user_id, dealer_id, business_name, exotel_virtual_number FROM users WHERE user_id = $1;", user_id)
    if user is None:
        raise credentials_exception
        
    user_dict = dict(user)
    # Ensure dealer_id is string if from token fallback
    if 'dealer_id' not in user_dict or not user_dict['dealer_id']:
        user_dict['dealer_id'] = dealer_id
    else:
        user_dict['dealer_id'] = str(user_dict['dealer_id'])
        
    return user_dict

class UserLogin(BaseModel):
    user_id: str
    password: str
    client_id: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict

class RefreshTokenReq(BaseModel):
    refresh_token: str
    client_id: str

class RefreshTokenRes(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

@router.post("/login", response_model=Token)
async def login_user(payload: UserLogin):
    """
    Logs in a user by their email-based user_id and password.
    """
    try:
        query = "SELECT user_id, dealer_id, business_name, password FROM users WHERE user_id = $1;"
        user = await fetchrow(query, payload.user_id.strip())
        
        if not user or not verify_password(payload.password, user.get('password')):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect user ID or password"
            )
            
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["user_id"], "dealer_id": str(user["dealer_id"])}, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(data={"sub": user["user_id"]})
        
        # Save refresh token hash to DB
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, client_id, last_used_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user["user_id"], token_hash, expires_at, payload.client_id
        )
        
        user_data = dict(user)
        user_data.pop('password', None) # Remove password from response
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/refresh", response_model=RefreshTokenRes)
async def refresh_token(payload: RefreshTokenReq):
    """
    Refreshes the access token using a valid refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if decoded.get("type") != "refresh":
            raise credentials_exception
            
        user_id: str = decoded.get("sub")
        if user_id is None:
            raise credentials_exception
            
        # Verify token exists and is valid in DB
        token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
        db_token = await fetchrow(
            """
            SELECT expires_at, client_id 
            FROM refresh_tokens 
            WHERE token_hash = $1 AND user_id = $2
            """,
            token_hash, user_id
        )
        
        if not db_token or db_token["expires_at"].replace(tzinfo=None) < datetime.utcnow():
            raise credentials_exception
            
        # Optionally verify client_id matches
        if db_token["client_id"] and db_token["client_id"] != payload.client_id:
            raise credentials_exception
            
        # Optional: check if user still exists
        user = await fetchrow("SELECT user_id, dealer_id FROM users WHERE user_id = $1;", user_id)
        if not user:
            raise credentials_exception
            
        # Delete old refresh token
        await execute("DELETE FROM refresh_tokens WHERE token_hash = $1", token_hash)
            
        # Issue new tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["user_id"], "dealer_id": str(user["dealer_id"])}, expires_delta=access_token_expires
        )
        new_refresh_token = create_refresh_token(data={"sub": user["user_id"]})
        
        new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        await execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, client_id, last_used_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user["user_id"], new_token_hash, expires_at, payload.client_id
        )
        
        return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}
        
    except jwt.PyJWTError:
        raise credentials_exception
