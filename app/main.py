from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.database import engine, Base
from app.routers import webhook
from app.routers.track import router as track_router
from app.services.scheduler import start_scheduler, stop_scheduler
from contextlib import asynccontextmanager
from app.routers.dashboard import router as dashboard_router

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="KiandaBot", version="0.1.0", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(track_router)
app.include_router(dashboard_router)

@app.get("/")
@app.head("/")
def root():
    return {"status": "ok", "app": "KiandaBot"}

@app.get("/health")
@app.head("/health")
def health():
    return {"status": "healthy"}