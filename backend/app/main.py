from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import create_db_and_tables
from app.routers import auth, jobs

app = FastAPI(title="SmartScout API")

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

app.include_router(auth.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Garante que as pastas de upload existem
    Path("uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("uploads/clips").mkdir(parents=True, exist_ok=True)


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/stream")
async def stream_numbers():
    async def gen():
        for i in range(1, 11):
            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
        yield "event: done\ndata: finished\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")