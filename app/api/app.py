from fastapi import FastAPI

from api.routes import books, chapters

app = FastAPI(
    title="Book TTS API",
    version="0.1.0"
)

app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
