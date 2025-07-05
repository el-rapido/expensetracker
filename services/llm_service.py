import json
import logging
import google.generativeai as genai
from datetime import datetime
import re

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

IMPORTANT: Turkish dates use DD/MM/YY or DD.MM.YY format (day first, then month). Convert to YYYY-MM-DD format carefully.

OCR Text:
{ocr_text}

Extract and return ONLY a valid JSON object with these fields:
{{
    "merchant_name": "cleaned merchant/store name",
    "total_amount": float value in Turkish Lira,
    "date": "YYYY-MM-DD format (CRITICAL: Turkish format is DD/MM/YY - day comes first!)",
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

CRITICAL DATE RULES:
- Turkish receipts use DD/MM/YY format (day first!)
- Example: "15/03/25" means March 15, 2025 (not September 15, 2025)
- Example: "05.07.24" means July 5, 2024 (not May 7, 2024)
- Convert to YYYY-MM-DD: "15/03/25" → "2025-03-15"
- If date is unclear, use today's date ({datetime.now().strftime('%Y-%m-%d')})

Other Rules:
- Convert Turkish number format (25,40) to decimal (25.40)
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
        """Enhanced validation with Turkish date format handling"""
        
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
        
        # ENHANCED DATE VALIDATION
        if data['date']:
            try:
                # Try to parse the provided date
                parsed_date = datetime.strptime(data['date'], '%Y-%m-%d')
                
                # Check if date is reasonable (not too far in future/past)
                today = datetime.now()
                days_diff = abs((parsed_date - today).days)
                
                if days_diff > 365:  # More than 1 year difference
                    logger.warning(f"Date seems incorrect: {data['date']}, using today's date")
                    data['date'] = today.strftime('%Y-%m-%d')
                    data['confidence'] = 'medium'
                    if 'extraction_notes' not in data:
                        data['extraction_notes'] = ""
                    data['extraction_notes'] += " Date adjusted (seemed incorrect)."
                
            except (ValueError, TypeError):
                # If date parsing fails, try common Turkish formats
                date_fixed = self.fix_turkish_date(data['date'])
                if date_fixed:
                    data['date'] = date_fixed
                    data['confidence'] = 'medium'
                    if 'extraction_notes' not in data:
                        data['extraction_notes'] = ""
                    data['extraction_notes'] += " Date format corrected."
                else:
                    # Use today's date as fallback
                    data['date'] = datetime.now().strftime('%Y-%m-%d')
                    data['confidence'] = 'medium'
                    if 'extraction_notes' not in data:
                        data['extraction_notes'] = ""
                    data['extraction_notes'] += " Date unclear, used today's date."
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
    
    def fix_turkish_date(self, date_str):
        """Fix Turkish date formats (DD/MM/YY or DD.MM.YY) to YYYY-MM-DD"""
        
        if not date_str:
            return None
        
        try:
            # Common Turkish date patterns
            
            # Pattern 1: DD/MM/YY or DD/MM/YYYY
            pattern1 = r'(\d{1,2})[\/](\d{1,2})[\/](\d{2,4})'
            match1 = re.search(pattern1, str(date_str))
            
            # Pattern 2: DD.MM.YY or DD.MM.YYYY  
            pattern2 = r'(\d{1,2})[.](\d{1,2})[.](\d{2,4})'
            match2 = re.search(pattern2, str(date_str))
            
            # Pattern 3: DD-MM-YY or DD-MM-YYYY
            pattern3 = r'(\d{1,2})[-](\d{1,2})[-](\d{2,4})'
            match3 = re.search(pattern3, str(date_str))
            
            match = match1 or match2 or match3
            
            if match:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                
                # Handle 2-digit years (assume 20xx for years 00-30, 19xx for 31-99)
                if year < 100:
                    if year <= 30:
                        year += 2000
                    else:
                        year += 1900
                
                # Validate day and month ranges
                if 1 <= day <= 31 and 1 <= month <= 12:
                    # Create date object to validate
                    test_date = datetime(year, month, day)
                    return test_date.strftime('%Y-%m-%d')
            
            return None
            
        except Exception as e:
            logger.error(f"Date fixing failed for '{date_str}': {e}")
            return None
    
    def create_confirmation_message(self, extracted_data):
        """Create English confirmation message with DD/MM/YYYY date format"""
        
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
        
        # CHANGED: Parse and format date as DD/MM/YYYY
        try:
            date_obj = datetime.strptime(data.get('date', ''), '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
        except:
            formatted_date = data.get('date', 'Unknown')
        
        message = f"""
{confidence_emoji.get(data.get('confidence', 'low'), '❓')} *Receipt Information*

🏪 *Merchant:* {data.get('merchant_name', 'Unknown')}
💰 *Total:* ₺{data.get('total_amount', 0):.2f}
📅 *Date:* {formatted_date}
{items_summary}

*Confidence:* {data.get('confidence', 'low').title()}

{data.get('extraction_notes', '')}

*Is this information correct?*
        """
        
        return message.strip()