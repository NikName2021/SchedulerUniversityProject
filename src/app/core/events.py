from typing import Callable

from database import create_tables
from fastapi import FastAPI

from core.config import engine


async def preload_model():
    await create_tables(engine)
    """
    In order to load model on memory to each worker
    """
    # from services import YoloModelHandler, FaceNetModel, RotateModel
    # YoloModelHandler.load_model()
    # FaceNetModel.load()
    # RotateModel.load()


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        await preload_model()

    return start_app
