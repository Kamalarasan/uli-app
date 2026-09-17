import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import wait_for_db, init_db, get_db
from app.rag.vector_store import vector_store
from app.config import settings
from app.routers import applications, documents, reports, simulator, observability
from app.models.orm import LoanApplication, UnderwritingReport
from app.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Loan Underwriting Platform...")
    wait_for_db()
    init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Initializing RAG vector store...")
    try:
        await vector_store.initialize()
        logger.info("Vector store initialized.")
    except Exception as e:
        logger.warning(f"Vector store initialization failed (will use fallback): {e}")
    logger.info("Platform ready.")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="AI Loan Underwriting Platform",
    version="1.0.0",
    description="Production-grade AI-powered loan underwriting with 8-stage pipeline",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(applications.router)
app.include_router(documents.router)
app.include_router(reports.router)
app.include_router(simulator.router)
app.include_router(observability.router)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"message": "Resource not found"})

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return JSONResponse(status_code=500, content={"message": "Internal server error"})

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    db = SessionLocal()
    try:
        recent_apps = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).limit(10).all()
        total = db.query(LoanApplication).count()
        pending = db.query(LoanApplication).filter(LoanApplication.status == "PENDING").count()
        approved = db.query(LoanApplication).filter(LoanApplication.status == "APPROVED").count()
        rejected = db.query(LoanApplication).filter(LoanApplication.status == "REJECTED").count()
        review = db.query(LoanApplication).filter(LoanApplication.status == "REVIEW").count()
        stats = {"total": total, "pending": pending, "approved": approved, "rejected": rejected, "review": review}
        return templates.TemplateResponse("dashboard.html", {"request": request, "applications": recent_apps, "stats": stats})
    finally:
        db.close()

@app.get("/app/new", response_class=HTMLResponse)
async def new_application(request: Request):
    return templates.TemplateResponse("new_application.html", {"request": request})

@app.get("/app/report/{id}", response_class=HTMLResponse)
async def get_report_page(request: Request, id: int):
    db = SessionLocal()
    try:
        app_data = db.query(LoanApplication).filter(LoanApplication.id == id).first()
        if not app_data:
            return HTMLResponse(status_code=404, content="<h1>Application not found</h1>")
            
        report = db.query(UnderwritingReport).filter(UnderwritingReport.application_id == id).first()
        
        radar_data = [
            report.health_score or 70 if report else 70,
            80,
            75,
            85,
            100 - (report.risk_score or 30) if report else 70
        ]
        
        decision_badge = "success" if report and report.decision == "APPROVED" else "danger" if report and report.decision == "REJECTED" else "warning"
        
        return templates.TemplateResponse("report.html", {
            "request": request,
            "application": app_data,
            "report": report,
            "radar_data": radar_data,
            "decision_badge": decision_badge
        })
    finally:
        db.close()

@app.get("/app/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request):
    db = SessionLocal()
    try:
        apps = db.query(LoanApplication).filter(LoanApplication.status.in_(["APPROVED", "REVIEW", "REJECTED"])).all()
        return templates.TemplateResponse("simulator.html", {"request": request, "applications": apps})
    finally:
        db.close()

@app.get("/app/observability", response_class=HTMLResponse)
async def observability_page(request: Request):
    return templates.TemplateResponse("observability.html", {"request": request})

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
