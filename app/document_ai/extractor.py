import os
import logging
from PIL import Image, ImageEnhance
import pdfplumber
import PyPDF2
import pytesseract

logger = logging.getLogger(__name__)

def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    try:
        gray_image = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray_image)
        enhanced_image = enhancer.enhance(2.0)
        return enhanced_image
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return image

async def extract_text(file_path: str, mime_type: str) -> str:
    if not os.path.exists(file_path):
        return ""
        
    extracted_text = ""
    
    try:
        if mime_type == 'application/pdf' or file_path.lower().endswith('.pdf'):
            try:
                with pdfplumber.open(file_path) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pages_text.append(text)
                    extracted_text = "\n".join(pages_text)
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}")
                
            if not extracted_text.strip():
                try:
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        pages_text = []
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                pages_text.append(text)
                        extracted_text = "\n".join(pages_text)
                except Exception as e:
                    logger.warning(f"PyPDF2 failed: {e}")
                    
        elif mime_type.startswith('image/') or file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                image = Image.open(file_path)
                processed = preprocess_image_for_ocr(image)
                extracted_text = pytesseract.image_to_string(processed)
            except Exception as e:
                logger.warning(f"pytesseract failed: {e}")
                
    except Exception as e:
        logger.error(f"Extraction error on {file_path}: {e}")
        
    return "\n".join(line.strip() for line in extracted_text.splitlines() if line.strip())
