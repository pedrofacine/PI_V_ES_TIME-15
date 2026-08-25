import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.database import create_db_and_tables
from app.core.exceptions import DomainError
from app.routers import jobs, clips
from app.modules.identity.router import router as identity_router

from ml.scripts.process_video import _get_pipeline

app = FastAPI(title="SmartScout API")


@app.exception_handler(DomainError)
def handle_domain_error(request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(identity_router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Garante que as pastas de upload existem
    Path("uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("uploads/clips").mkdir(parents=True, exist_ok=True)

    print("[SISTEMA] Iniciando aquecimento da IA (carregando modelos)...")
    _get_pipeline()
    print("[SISTEMA] IA carregada na memória e pronta para uso!")


app.mount("/api/v1/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/stream")
async def stream_numbers():
    async def gen():
        for i in range(1, 11):
            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
        yield "event: done\ndata: finished\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")