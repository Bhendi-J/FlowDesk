from fastapi import APIRouter, HTTPException, Depends
from app.database import DBsession
from app.models.users import User
from app.schemas.users import (
    UserCreate, 
    UserBase, 
    UserRead, 
    UserUpdate
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@router.post("/", response_model=UserRead)
def create_user(
    user_data:UserCreate,
    db:DBsession
):
    user = User(
        name = user_data.name,
        email = user_data.email,
        password_hash = user_data.password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id:int,
    db:DBsession
):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="user not found"
        )
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: DBsession
):
    update_data = user_data.model_dump(exclude_unset=True)
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="user not found"
        )
    
    for key, value in update_data.items():
        setattr(user, key, value)


    db.commit()
    db.refresh(user)

    return user

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: DBsession
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="user not found"
        )
    
    db.delete(user)
    db.commit()

    return {"message": "User deleted"}

