import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # API Keys
    WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Exchange Rates
    POS_RATE = float(os.getenv('POS_RATE', 34.85))
    ATM_RATE = float(os.getenv('ATM_RATE', 34.92))
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local_development.db')