import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.exceptions import DomainError
from app.modules.clips.router import router as clips_jobs_router, clips_router
from app.modules.identity.router import router as identity_router

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
app.include_router(clips_jobs_router, prefix="/api/v1")
app.include_router(clips_router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    # Schema agora é gerido por Alembic (migrações versionadas), não mais create_all.
    # Garante que as pastas de upload existem
    Path("uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("uploads/clips").mkdir(parents=True, exist_ok=True)


app.mount("/api/v1/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/stream")
async def stream_numbers():
    async def gen():
        for i in range(1, 11):
            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
        yield "event: done\ndata: finished\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")