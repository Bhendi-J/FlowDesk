from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.users import User
from app.models.workspaces import Workspace
from app.models.projects import Project
from app.models.tasks import Task
from app.models.dependencies import TaskDependency
from app.models.resources import Resource, TaskResourceRequirement


from app.routers.users import router as user_router
from app.routers.workspaces import router as workspace_router
from app.routers.projects import router as project_router
from app.routers.tasks import router as task_router
from app.routers.dependencies import router as dependency_router
from app.routers.cpm import router as cpm_router
from app.routers.schedule import router as schedule_router


from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(lifespan=lifespan)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(project_router)
app.include_router(task_router)
app.include_router(dependency_router)
app.include_router(cpm_router)
app.include_router(schedule_router)


@app.get("/")
def root():
    return {"message": "FlowDesk API is running"}
