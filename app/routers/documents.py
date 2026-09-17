from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.orm import Document, LoanApplication
from app.document_ai.extractor import extract_text
from app.document_ai.classifier import classify_and_extract
from app.config import settings
import os, shutil, uuid, logging, aiofiles

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

async def process_document_async(filepath: str, doc_id: int, db: Session):
    try:
        text = await extract_text(filepath)
        classification = await classify_and_extract(text)
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.extracted_text = text
            doc.classification_result = classification
            doc.processing_status = "COMPLETED"
            db.commit()
    except Exception as e:
        logger.error(f"Error processing doc: {e}")
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.processing_status = "FAILED"
            db.commit()

@router.post("/upload/{application_id}")
async def upload_document(
    application_id: int, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    doc_type: str = Form("UNKNOWN"),
    db: Session = Depends(get_db)
):
    app = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    app_dir = os.path.join(settings.UPLOAD_DIR, str(application_id))
    os.makedirs(app_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(app_dir, filename)
    
    async with aiofiles.open(filepath, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    doc = Document(
        application_id=application_id,
        document_type=doc_type,
        file_path=filepath,
        file_name=file.filename,
        processing_status="PROCESSING"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    background_tasks.add_task(process_document_async, filepath, doc.id, db)
    
    return {
        "id": doc.id,
        "doc_type": doc_type,
        "filename": file.filename,
        "processing_status": "PROCESSING"
    }

@router.get("/{application_id}")
def list_documents(application_id: int, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.application_id == application_id).all()
    return [{"id": d.id, "filename": d.file_name, "type": d.document_type, "status": d.processing_status} for d in docs]

@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
        
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}
