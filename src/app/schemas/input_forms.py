from typing import Optional, Union

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


def validate_file(file: Union[UploadFile, str, None]) -> Optional[UploadFile]:
    if file is None:
        return None
    if isinstance(file, str) and file == "":
        return None
    if isinstance(file, UploadFile) and not file.filename:
        return None
    return file


class EventCreateForm:
    def __init__(
        self,
        name: str = Form(...),
        date_str: str = Form(...),
        description: str = Form(...),
        image: Union[UploadFile, str, None] = File(None),
        csv_file: Union[UploadFile, str, None] = File(None),
    ):
        self.name = name
        self.date_str = date_str
        self.description = description
        self.image = validate_file(image)
        self.csv_file = validate_file(csv_file)


class EventUpdateForm:
    def __init__(
        self,
        name: Optional[str] = Form(None),
        date_str: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        image: Union[UploadFile, str, None] = File(None),
        csv_file: Union[UploadFile, str, None] = File(None),
    ):
        self.name = name
        self.date_str = date_str
        self.description = description
        self.image = validate_file(image)
        self.csv_file = validate_file(csv_file)
