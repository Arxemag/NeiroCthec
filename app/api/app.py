from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.books import router as books_router
from api.routes.internal import router as internal_router
from api.routes.test import router as test_router
from db.base import Base
from db.session import engine

app = FastAPI(title="NeiroCthec API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books_router, prefix="/books", tags=["books"])
app.include_router(internal_router, prefix="/internal", tags=["internal"])
app.include_router(test_router, prefix="/test", tags=["test"])


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
