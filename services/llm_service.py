import json
import logging
import google.generativeai as genai
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key):
        """Initialize Google Gemini client"""
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Google Gemini client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.model = None
    
    def process_receipt_text(self, ocr_text):
        """Process OCR text using LLM to extract structured data"""
        
        if not self.model:
            return {
                "success": False,
                "error": "LLM service not available",
                "confidence": "low"
            }
        
        prompt = f"""
You are a Turkish receipt processing expert. Analyze this OCR text from a Turkish receipt and extract the following information in JSON format.

OCR Text:
{ocr_text}

Extract and return ONLY a valid JSON object with these fields:
{{
    "merchant_name": "cleaned merchant/store name",
    "total_amount": float value in Turkish Lira,
    "date": "YYYY-MM-DD format (use today's date if unclear)",
    "items": [
        {{
            "name": "item name",
            "quantity": 1,
            "price": float value
        }}
    ],
    "receipt_number": "receipt/invoice number if found",
    "tax_amount": float value of KDV/tax if found,
    "confidence": "high/medium/low based on text quality",
    "currency": "TRY",
    "extraction_notes": "any issues or assumptions made"
}}

Rules:
- Convert Turkish number format (25,40) to decimal (25.40)
- If date is unclear, use today's date ({datetime.now().strftime('%Y-%m-%d')})
- Clean merchant name but keep it recognizable
- Set confidence based on OCR text clarity
- Handle Turkish characters properly (ç, ğ, ı, ö, ş, ü)
- Look for keywords: TOPLAM, FİŞ, TARİH, KDV, TUTAR
- If total amount not found, sum individual items
- Extract individual items with their prices
- Be conservative with confidence rating

Return only valid JSON, no other text or explanation.
        """
        
        try:
            response = self.model.generate_content(prompt)
            
            # Clean up the response text
            response_text = response.text.strip()
            
            # Remove any markdown formatting if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON response
            extracted_data = json.loads(response_text)
            
            # Validate the extracted data
            validated_data = self.validate_extracted_data(extracted_data)
            
            logger.info(f"LLM processing successful. Confidence: {validated_data.get('confidence', 'unknown')}")
            
            return {
                "success": True,
                "data": validated_data
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw response: {response.text}") # type: ignore
            return {
                "success": False,
                "error": f"Invalid JSON response: {str(e)}",
                "confidence": "low"
            }
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "confidence": "low"
            }
    
    def validate_extracted_data(self, data):
        """Basic validation of LLM extracted data"""
        
        # Ensure required fields exist
        required_fields = ['merchant_name', 'total_amount', 'date', 'confidence']
        for field in required_fields:
            if field not in data:
                data[field] = None
        
        # Validate amount
        if data['total_amount']:
            try:
                data['total_amount'] = float(data['total_amount'])
                if data['total_amount'] <= 0:
                    data['confidence'] = 'low'
            except (ValueError, TypeError):
                data['total_amount'] = None
                data['confidence'] = 'low'
        
        # Validate date
        if data['date']:
            try:
                datetime.strptime(data['date'], '%Y-%m-%d')
            except (ValueError, TypeError):
                data['date'] = datetime.now().strftime('%Y-%m-%d')
                data['confidence'] = 'medium'
        else:
            data['date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Validate items
        if not isinstance(data.get('items'), list):
            data['items'] = []
        
        # Validate confidence
        if data['confidence'] not in ['high', 'medium', 'low']:
            data['confidence'] = 'medium'
        
        # Ensure merchant name is not empty
        if not data['merchant_name'] or data['merchant_name'].strip() == '':
            data['merchant_name'] = 'Unknown Merchant'
            data['confidence'] = 'low'
        
        return data
    
    def create_confirmation_message(self, extracted_data):
        """Create English confirmation message"""
        
        if not extracted_data.get('success'):
            return f"❌ Receipt processing failed: {extracted_data.get('error', 'Unknown error')}"
        
        data = extracted_data['data']
        
        confidence_emoji = {
            'high': '✅',
            'medium': '⚠️', 
            'low': '❌'
        }
        
        items_summary = ""
        if data.get('items') and len(data['items']) > 0:
            items_count = len(data['items'])
            items_summary = f"\n🛍️ *Items:* {items_count} items"
            
            # Show first few items
            if items_count <= 3:
                for item in data['items']:
                    items_summary += f"\n   • {item.get('name', 'Unknown')} - ₺{item.get('price', 0):.2f}"
            else:
                for item in data['items'][:2]:
                    items_summary += f"\n   • {item.get('name', 'Unknown')} - ₺{item.get('price', 0):.2f}"
                items_summary += f"\n   • ... and {items_count - 2} more items"
        
        message = f"""
{confidence_emoji.get(data.get('confidence', 'low'), '❓')} *Receipt Information*

🏪 *Merchant:* {data.get('merchant_name', 'Unknown')}
💰 *Total:* ₺{data.get('total_amount', 0):.2f}
📅 *Date:* {data.get('date', 'Unknown')}
{items_summary}

*Confidence:* {data.get('confidence', 'low').title()}

{data.get('extraction_notes', '')}

*Is this information correct?*
        """
        
        return message.strip()