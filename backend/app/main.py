from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.models.users import User
from app.models.workspaces import Workspace
from app.models.projects import Project
from app.models.tasks import Task
from app.models.dependencies import TaskDependency


from app.routers.users import router as user_router
from app.routers.workspaces import router as workspace_router
from app.routers.projects import router as project_router
from app.routers.tasks import router as task_router
from app.routers.dependencies import router as dependency_router


from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(project_router)
app.include_router(task_router)
app.include_router(dependency_router)



@app.get("/")
def root():
    return {"message": "FlowDesk API is running"}