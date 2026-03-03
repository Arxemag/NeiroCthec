from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import books, chapters, voices

app = FastAPI(
    title="Book TTS API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(voices.router, tags=["voices"])
