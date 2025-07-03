import logging
import os
import json
import io
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        """Initialize Google Cloud Vision client"""
        try:
            # Method 1: Try environment variable (for production)
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            
            if credentials_json:
                logger.info("Using Google credentials from environment variable")
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                self.client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.info("Google Cloud Vision client initialized from environment")
                
            # Method 2: Try file (for local development)
            elif os.path.exists('google-credentials.json'):
                logger.info("Using Google credentials from file")
                self.client = vision.ImageAnnotatorClient.from_service_account_file('google-credentials.json')
                logger.info("Google Cloud Vision client initialized from file")
                
            # Method 3: Try default credentials (for Google Cloud deployment)
            else:
                logger.info("Trying default Google credentials")
                self.client = vision.ImageAnnotatorClient()
                logger.info("Google Cloud Vision client initialized with default credentials")
                
        except Exception as e:
            logger.error(f"Failed to initialize Vision client: {e}")
            logger.error(f"GOOGLE_CREDENTIALS_JSON set: {bool(os.getenv('GOOGLE_CREDENTIALS_JSON'))}")
            logger.error(f"google-credentials.json exists: {os.path.exists('google-credentials.json')}")
            self.client = None
    
    def extract_text_from_image(self, image_data):
        """Extract text from image using Google Cloud Vision"""
        
        if not self.client:
            return {
                "success": False,
                "error": "OCR service not available - Google credentials not configured",
                "text": "",
                "confidence": 0
            }
        
        try:
            # Create Vision API image object
            image = vision.Image(content=image_data)
            
            # Configure for Turkish language
            image_context = vision.ImageContext(
                language_hints=['tr']  # Turkish language hint
            )
            
            # Perform text detection
            response = self.client.text_detection( # type: ignore
                image=image,
                image_context=image_context
            )
            
            # Check for errors
            if response.error.message:
                raise Exception(f'{response.error.message}')
            
            # Extract text
            texts = response.text_annotations
            
            if texts:
                # First annotation contains all detected text
                full_text = texts[0].description
                
                # Calculate confidence (average of all detected words)
                confidence = self.calculate_confidence(texts)
                
                logger.info(f"OCR successful. Text length: {len(full_text)}, Confidence: {confidence}")
                
                return {
                    "success": True,
                    "text": full_text,
                    "confidence": confidence,
                    "word_count": len(full_text.split()) if full_text else 0
                }
            else:
                return {
                    "success": False,
                    "error": "No text detected in image",
                    "text": "",
                    "confidence": 0
                }
                
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0
            }
    
    def calculate_confidence(self, text_annotations):
        """Calculate average confidence from text annotations"""
        if len(text_annotations) <= 1:
            return 0.8  # Default confidence if no individual word confidence
        
        # Skip first annotation (full text) and calculate average
        confidences = []
        for annotation in text_annotations[1:]:  # Skip first one
            if hasattr(annotation, 'confidence'):
                confidences.append(annotation.confidence)
        
        if confidences:
            return sum(confidences) / len(confidences)
        else:
            return 0.8  # Default confidence
    
    def preprocess_image(self, image_data):
        """Basic image preprocessing for better OCR results"""
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Basic enhancement could be added here
            # For now, just return as is
            
            # Convert back to bytes
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=95)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image_data  # Return original if preprocessing fails