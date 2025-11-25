from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import upload, reports, analysis, system, settings, integrations
from backend.database.database import engine, Base
import os

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GMS Certification Analyzer", version="1.0.0")

# CORS configuration
origins = [
    "http://localhost:5173",  # React dev server (kept for reference)
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('backend/static/index.html')

