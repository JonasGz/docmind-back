from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import auth, documents
from app.storage.s3 import storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.garantir_bucket()
    yield


app = FastAPI(title="DocMind API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
