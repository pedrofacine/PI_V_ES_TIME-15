import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.routers import auth

app = FastAPI()

app.include_router(auth.router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

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

@app.get("/stream")
async def stream_numbers():
    async def gen():
        for i in range(1, 11):
            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
        yield "event: done\ndata: finished\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")