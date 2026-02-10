from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import upload, reports, analysis, system, settings, integrations, import_json, submissions, config, export
from backend.database.database import engine, Base
import os

# Run database migrations
try:
    from migrate_db import migrate
    migrate()
except ImportError:
    # Fallback for different execution contexts
    import sys
    sys.path.append(os.getcwd())
    try:
        from migrate_db import migrate
        migrate()
    except Exception as e:
        print(f"Database migration failed to start: {e}")

# Create database tables
Base.metadata.create_all(bind=engine)

# Auto-bootstrap standard data
try:
    from backend.database.bootstrap import bootstrap_database
    bootstrap_database()
except Exception as e:
    print(f"Failed to bootstrap database: {e}")

app = FastAPI(title="CTS Insight", version="1.0.0")

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
app.include_router(import_json.router, prefix="/api/import", tags=["Import"])
app.include_router(submissions.router, prefix="/api/submissions", tags=["Submissions"])
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return FileResponse('backend/static/index.html')

