import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User
from app.utils.password import hash_password, verify_password
from typing import Optional, List
from uuid import UUID
from fastapi import HTTPException, status
from app.schemas.user_schemas import UserRegister, UserUpdate, PasswordChange
from datetime import datetime
from datetime import timedelta
from sqlalchemy.exc import IntegrityError 

Logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    async def register_user(db: AsyncSession, user_data: UserRegister) -> User:
        """
        Register a new user with activation
        """
        try:
            # 1. Validate mobile number uniqueness
            result = await db.execute(
                select(User).where(User.mobile_number == user_data.mobile_number)
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400, 
                    detail="Mobile number already registered"
                )
            
            # 2. Validate email uniqueness (if provided)
            if user_data.email:
                result = await db.execute(
                    select(User).where(User.email == user_data.email)
                )
                if result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=400, 
                        detail="Email already registered"
                    )
            
            # 3. Create user instance
            user = User(
                mobile_number=user_data.mobile_number,
                password_hash=hash_password(user_data.password),
                full_name=user_data.full_name,
                email=user_data.email,
                is_active=True
            )
            
            # 4. Add user to session and flush to get ID
            db.add(user)
            await db.flush() 
            
            # 5. Commit user
            await db.commit()
            await db.refresh(user)
            
            Logger.info(f"User registered successfully: {user.mobile_number}")
            return user
            
        except HTTPException:
            await db.rollback()
            raise
        except IntegrityError as e:
            await db.rollback()
            if "mobile_number" in str(e.orig):
                raise HTTPException(
                    status_code=400,
                    detail="Mobile number already registered"
                )
            elif "email" in str(e.orig):
                raise HTTPException(
                    status_code=400,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Registration failed due to data conflict"
                )
        except Exception as e:
            await db.rollback()
            Logger.error(f"User registration failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="User registration failed"
            )

    @staticmethod
    async def change_password(db: AsyncSession, user_id: UUID, data: PasswordChange) -> None:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not verify_password(data.old_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user.password_hash = hash_password(data.new_password)
        await db.commit()

    @staticmethod
    async def get_profile(db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_profile_by_mobile_number(db: AsyncSession, mobile_number: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.mobile_number == mobile_number))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_profile(db: AsyncSession, user_id: UUID, data: UserUpdate) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, mobile_number: str, password: str) -> User:
        """Authenticate a user by mobile number and password."""
        result = await db.execute(select(User).where(User.mobile_number == mobile_number))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User is inactive")
        return user

    @staticmethod
    async def set_active(db: AsyncSession, user_id: UUID, active: bool) -> None:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_active = active
        await db.commit()

    @staticmethod
    async def search_users(db: AsyncSession, mobile: Optional[str] = None, email: Optional[str] = None) -> List[User]:
        query = select(User)
        if mobile:
            query = query.where(User.mobile_number == mobile)
        if email:
            query = query.where(User.email == email)
        result = await db.execute(query)
        return result.scalars().all()
