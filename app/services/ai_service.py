"""
Enhanced AI Service with Robust Model Validation and Error Handling

Handles all AI-related operations including:
- Text generation (job descriptions, feedback)
- Resume analysis
- Interview question generation
- Document processing
"""

import os
import re
import json
import logging
import time
from typing import List, Dict, Tuple, Optional, Union
import ollama
import requests
from PyPDF2 import PdfReader, PdfReadError
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from PIL import Image, UnidentifiedImageError
import pytesseract
from app.utils.config import settings
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import spacy
from fastapi import HTTPException
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, ollama_base_url: str = None, ollama_model: str = None, 
                 hf_api_token: str = None, hf_model: str = None):
        """
        Initialize AI service with configurable model endpoints
        
        Args:
            ollama_base_url: Base URL for Ollama server
            ollama_model: Model name for Ollama
            hf_api_token: HuggingFace API token
            hf_model: HuggingFace model name
        """
        self.ollama_base_url = ollama_base_url or settings.OLLAMA_BASE_URL
        self.ollama_model = ollama_model or settings.OLLAMA_MODEL
        self.hf_api_token = hf_api_token or settings.HF_API_TOKEN
        self.hf_model = hf_model or settings.HF_MODEL
        
        self._initialize_ocr()
        self._load_models()
        self._initialize_caches()
        self.last_api_call = datetime.min
        self.model_initialized = False

    def _initialize_ocr(self):
        """Initialize OCR configuration with validation"""
        try:
            if settings.TESSERACT_PATH and os.path.exists(settings.TESSERACT_PATH):
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            elif os.name == 'nt':  # Windows default path
                default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                if os.path.exists(default_path):
                    pytesseract.pytesseract.tesseract_cmd = default_path
                else:
                    raise RuntimeError("Tesseract OCR not found at default location")
            else:
                # Try system PATH
                try:
                    pytesseract.get_tesseract_version()
                except EnvironmentError:
                    raise RuntimeError("Tesseract OCR not found in PATH")
                    
        except Exception as e:
            logger.error(f"OCR initialization failed: {str(e)}")
            raise RuntimeError("Failed to initialize OCR system") from e

    def _load_models(self):
        """Load required AI models with comprehensive error handling"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Loading AI models (attempt {attempt + 1})")
                
                # Validate embedding model
                self.embedding_model = SentenceTransformer(
                    settings.EMBEDDING_MODEL or 'all-MiniLM-L6-v2',
                    device='cuda' if settings.USE_GPU else 'cpu'
                )
                self._validate_embedding_model()
                
                # Validate NLP model
                self.nlp = spacy.load(settings.SPACY_MODEL or "en_core_web_sm")
                self._validate_nlp_model()
                
                # Add skill patterns
                ruler = self.nlp.add_pipe("entity_ruler")
                patterns = [{"label": "SKILL", "pattern": skill.lower()} 
                          for skill in self._load_skill_patterns()]
                ruler.add_patterns(patterns)
                
                self.model_initialized = True
                logger.info("AI models loaded successfully")
                return
                
            except Exception as e:
                logger.error(f"Model loading failed (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    logger.critical("Failed to load AI models after multiple attempts")
                    raise RuntimeError("Failed to initialize AI models") from e
                time.sleep(retry_delay)

    def _validate_embedding_model(self):
        """Validate embedding model is working"""
        test_text = "validate embedding model"
        try:
            embedding = self.embedding_model.encode(test_text)
            if len(embedding) < 10:  # Simple sanity check
                raise ValueError("Invalid embedding generated")
        except Exception as e:
            logger.error(f"Embedding model validation failed: {str(e)}")
            raise RuntimeError("Embedding model validation failed") from e

    def _validate_nlp_model(self):
        """Validate NLP model is working"""
        test_text = "validate nlp model"
        try:
            doc = self.nlp(test_text)
            if not doc or len(doc) != 3:  # Simple sanity check
                raise ValueError("Invalid NLP processing")
        except Exception as e:
            logger.error(f"NLP model validation failed: {str(e)}")
            raise RuntimeError("NLP model validation failed") from e

    def _load_skill_patterns(self) -> List[str]:
        """Load skill patterns with validation"""
        try:
            if os.path.exists("data/skills.json"):
                with open("data/skills.json", "r") as f:
                    skills = json.load(f)
                    if not isinstance(skills, list):
                        raise ValueError("Skills file should contain a list")
                    return skills
        except Exception as e:
            logger.warning(f"Failed to load custom skills: {str(e)}")
        
        # Default fallback skills
        return [
            "machine learning", "python", "sql", "aws",
            "docker", "kubernetes", "react", "node.js",
            "project management", "agile", "scrum"
        ]

    def _initialize_caches(self):
        """Initialize caches with size limits"""
        from cachetools import TTLCache
        self.job_embedding_cache = TTLCache(
            maxsize=settings.EMBEDDING_CACHE_SIZE or 100,
            ttl=settings.EMBEDDING_CACHE_TTL or 3600
        )
        self.resume_embedding_cache = TTLCache(
            maxsize=settings.EMBEDDING_CACHE_SIZE or 100,
            ttl=settings.EMBEDDING_CACHE_TTL or 3600
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HTTPException),
        reraise=True
    )
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract and clean text from various file formats with robust error handling
        
        Args:
            file_path: Path to the file (PDF, DOCX, or image)
            
        Returns:
            Extracted and cleaned text
            
        Raises:
            HTTPException: If file processing fails
        """
        try:
            # Validate file exists and is accessible
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=400,
                    detail="File not found"
                )
            if not os.access(file_path, os.R_OK):
                raise HTTPException(
                    status_code=403,
                    detail="File access denied"
                )

            file_ext = os.path.splitext(file_path)[1].lower()
            text = ""

            # Dispatch to appropriate parser
            if file_ext == '.pdf':
                text = self._extract_pdf_text(file_path)
            elif file_ext in ('.docx', '.doc'):
                text = self._extract_docx_text(file_path)
            elif file_ext in ('.png', '.jpg', '.jpeg'):
                text = self._extract_image_text(file_path)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}"
                )

            cleaned_text = self._clean_text(text)
            if not cleaned_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="No readable text found in document"
                )

            return cleaned_text

        except HTTPException:
            raise
        except PdfReadError as e:
            logger.error(f"PDF parsing error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail="Invalid PDF file - may be corrupted or encrypted"
            )
        except PackageNotFoundError as e:
            logger.error(f"DOCX parsing error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail="Invalid DOCX file - may be corrupted"
            )
        except UnidentifiedImageError as e:
            logger.error(f"Image parsing error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail="Invalid image file - may be corrupted"
            )
        except Exception as e:
            logger.error(f"Unexpected file processing error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process document: {str(e)}"
            )

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF with PyPDF2"""
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            return "\n".join(
                page.extract_text() or "" 
                for page in reader.pages
            )

    def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX with python-docx"""
        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)

    def _extract_image_text(self, file_path: str) -> str:
        """Extract text from image with Tesseract OCR"""
        image = Image.open(file_path)
        # Preprocess image for better OCR
        image = image.convert('L')  # Convert to grayscale
        return pytesseract.image_to_string(image)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace and non-printable chars
        text = re.sub(r'\s+', ' ', text).strip()
        text = ''.join(char for char in text if char.isprintable())
        
        # Normalize unicode characters
        text = text.encode('ascii', 'ignore').decode('ascii')
        return text

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type(HTTPException),
        reraise=True
    )
    async def generate_job_description(
        self,
        job_title: str,
        department: str,
        skills: List[str],
        tone: str = "professional",
        length: str = "medium"
    ) -> str:
        """
        Generate a professional job description using AI
        
        Args:
            job_title: Title of the job
            department: Department the job belongs to
            skills: List of required skills
            tone: Writing style ('professional', 'friendly', 'formal')
            length: Description length ('short', 'medium', 'detailed')
            
        Returns:
            Generated job description
            
        Raises:
            HTTPException: If generation fails
        """
        # Validate inputs
        if not job_title or not department or not skills:
            raise HTTPException(
                status_code=400,
                detail="Job title, department and skills are required"
            )

        if tone not in ["professional", "friendly", "formal"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid tone specified"
            )

        if length not in ["short", "medium", "detailed"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid length specified"
            )

        prompt = self._build_job_description_prompt(
            job_title, department, skills, tone, length
        )

        try:
            self._rate_limit_check()
            
            if self.hf_api_token and self.hf_model:
                return await self._generate_with_huggingface(prompt)
            return await self._generate_with_ollama(prompt)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Job description generation failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate job description"
            )

    # ... [rest of the methods with similar enhanced error handling] ...

    async def _generate_with_ollama(
        self,
        prompt: str,
        json_output: bool = False
    ) -> str:
        """Generate text using Ollama local LLM with validation"""
        if not self.model_initialized:
            raise HTTPException(
                status_code=503,
                detail="AI models not initialized"
            )

        try:
            # Validate Ollama connection
            try:
                available_models = ollama.list()
                if not any(m['name'] == self.ollama_model for m in available_models.get('models', [])):
                    raise HTTPException(
                        status_code=503,
                        detail=f"Model {self.ollama_model} not available in Ollama"
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Ollama connection failed: {str(e)}"
                )

            response = ollama.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.3 if json_output else 0.7,
                    "format": "json" if json_output else None
                }
            )
            
            content = response["message"]["content"]
            if not content:
                raise ValueError("Empty response from Ollama")
                
            return content
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ollama generation failed: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="AI service unavailable"
            )

    async def _generate_with_huggingface(
        self,
        prompt: str,
        json_output: bool = False
    ) -> str:
        """Generate text using HuggingFace API with validation"""
        if not self.hf_api_token:
            raise HTTPException(
                status_code=503,
                detail="HuggingFace API not configured"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self.hf_api_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 1024,
                    "temperature": 0.3 if json_output else 0.7,
                    "return_full_text": False
                }
            }
            
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{self.hf_model}",
                headers=headers,
                json=data,
                timeout=30
            )
            
            # Handle API errors
            if response.status_code != 200:
                error_msg = response.json().get("error", "Unknown error")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"HuggingFace API error: {error_msg}"
                )
                
            result = response.json()
            if not result or not isinstance(result, list):
                raise ValueError("Invalid response format from HuggingFace")
                
            return result[0]["generated_text"]
            
        except HTTPException:
            raise
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail="HuggingFace API timeout"
            )
        except Exception as e:
            logger.error(f"HuggingFace API failed: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail="AI API service unavailable"
            )