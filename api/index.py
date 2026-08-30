from fastapi import FastAPI

from backend.routes import properties_router

app = FastAPI(
    title="Plot Twist API",
    version="0.1.0",
)

app.include_router(properties_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "plot-twist-api",
    }
