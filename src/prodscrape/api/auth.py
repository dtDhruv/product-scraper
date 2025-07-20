from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, status, APIRouter
from fastapi.exceptions import HTTPException
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from typing import Optional, Callable
from asyncpg import Pool

load_dotenv(override=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(pool: Pool, username: str):
    async with pool.acquire() as conn:
        query = """
        SELECT username, email, full_name, hashed_password, disabled 
        FROM users 
        WHERE username = $1
        """
        row = await conn.fetchrow(query, username)

        if row:
            return UserInDB(
                username=row["username"],
                email=row["email"],
                full_name=row["full_name"],
                hashed_password=row["hashed_password"],
                disabled=row["disabled"],
            )
        return None


async def authenticate_user(pool: Pool, username: str, password: str):
    user = await get_user(pool, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, os.getenv("API_SECRET_KEY"), algorithm=os.getenv("ALGORITHM")
    )
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    pool: Pool = Depends(lambda: None),
):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            os.getenv("API_SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM")],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)

    except JWTError:
        raise credential_exception

    user = await get_user(pool, username=token_data.username)
    if user is None:
        raise credential_exception

    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


class AmazonProduct(BaseModel):
    asin: str


class AuthRouter(APIRouter):
    def __init__(self, pool_provider: Callable[[], Pool]):
        super().__init__(prefix="")
        self.pool_provider = pool_provider

        def get_pool():
            return self.pool_provider()

        async def get_current_user_with_pool(token: str = Depends(oauth2_scheme)):
            return await get_current_user(token, get_pool())

        async def get_current_active_user_with_pool():
            current_user = await get_current_user_with_pool()
            if current_user.disabled:
                raise HTTPException(status_code=400, detail="Inactive user")
            return current_user

        self.add_api_route(
            "/token",
            self.login_for_access_token,
            methods=["POST"],
            response_model=Token,
        )

        self.add_api_route(
            "/users/me/",
            self.read_users_me,
            methods=["GET"],
            response_model=User,
            dependencies=[Depends(get_current_active_user_with_pool)],
        )

    async def login_for_access_token(
        self, form_data: OAuth2PasswordRequestForm = Depends()
    ):
        pool = self.pool_provider()
        user = await authenticate_user(pool, form_data.username, form_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(
            minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        )
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

    async def read_users_me(
        self, current_user: User = Depends(get_current_active_user)
    ):
        return current_user
