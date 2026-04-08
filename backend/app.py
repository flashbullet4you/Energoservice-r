"""Главный файл приложения — только запуск и настройка FastAPI."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import logger
from indexer import setup_scheduler
from routes import (
    health_handler,
    dashboard_handler,
    ready_handler,
    trigger_index,
    query_handler,
)


# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск и остановка приложения."""
    logger.info("🚀 Запуск приложения. Провайдер: Yandex AI Studio")
    scheduler = setup_scheduler()
    yield
    logger.info("🛑 Остановка приложения...")
    scheduler.shutdown(wait=False)


# ==================== FASTAPI APP ====================
app = FastAPI(title="DocSearch MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MIDDLEWARE ====================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = f"{(time.time() - start):.2f}s"
    logger.info(
        f"{request.method} {request.url.path} | {response.status_code} | {duration}"
    )
    return response


# ==================== ROUTES ====================
app.get("/api/health")(health_handler)
app.get("/dashboard")(dashboard_handler)
app.get("/api/ready")(ready_handler)
app.post("/api/index")(trigger_index)
app.post("/api/query")(query_handler)


# ==================== RUN ====================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
