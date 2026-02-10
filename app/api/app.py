from fastapi import FastAPI

from api.routes.books import router as books_router
from api.routes.chapters import router as chapters_router

app = FastAPI(title="NeiroCthec API")
app.include_router(books_router, prefix="/books", tags=["books"])
app.include_router(chapters_router, prefix="/chapters", tags=["chapters"])
