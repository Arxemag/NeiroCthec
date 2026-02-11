from fastapi import FastAPI

from api.routes.books import router as books_router
from api.routes.internal import router as internal_router
from db.base import Base
from db.session import engine

app = FastAPI(title="NeiroCthec API")
app.include_router(books_router, prefix="/books", tags=["books"])
app.include_router(internal_router, prefix="/internal", tags=["internal"])


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
