import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import app_pipeline, books, chapters, voices

app = FastAPI(
    title="Book TTS API",
    version="0.1.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}


# CORS: в Docker приложение могут открывать по IP (например http://192.168.1.5:3000).
# CORS_ORIGIN_REGEX переопределяет регулярку для origin (по умолчанию — localhost и любой хост).
_cors_origin_regex = (
    os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    or r"^https?://(localhost|127\.0\.0\.1|[\w.-]+)(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=_cors_origin_regex,
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
app.include_router(app_pipeline.tasks_router, tags=["tasks"])
