import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/stream")
async def stream_numbers():
    async def gen():
        for i in range(1, 11):
            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
        yield "event: done\ndata: finished\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")