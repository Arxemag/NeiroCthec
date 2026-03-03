from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import app_pipeline, books, chapters, voices

app = FastAPI(
    title="Book TTS API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(voices.router, tags=["voices"])
app.include_router(app_pipeline.books_router, prefix="/books", tags=["books-extra"])
app.include_router(app_pipeline.internal_router, prefix="/internal", tags=["internal"])
