from flask import Flask, request, jsonify
from config import Config
from models import db, User, Expense
from services.database_service import DatabaseService
from services.whatsapp_service import WhatsAppService
from services.message_handler import MessageHandler
from datetime import datetime
import logging
from services.ocr_service import OCRService
from dotenv import load_dotenv
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Database setup
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['DATABASE_URL']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
   # Initialize WhatsApp service (only if credentials are available)
    whatsapp_service = None
    message_handler = None
    
   #Initialize OCR Service
    ocr_service = OCRService()

    if app.config.get('WHATSAPP_ACCESS_TOKEN') and app.config.get('WHATSAPP_PHONE_NUMBER_ID'):
        try:
            whatsapp_service = WhatsAppService(
                app.config['WHATSAPP_ACCESS_TOKEN'],
                app.config['WHATSAPP_PHONE_NUMBER_ID']
            )
            message_handler = MessageHandler(whatsapp_service)
            logger.info("WhatsApp service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp service: {e}")
            whatsapp_service = None
            message_handler = None
    else:
        logger.warning("WhatsApp credentials not found - running without WhatsApp integration")
        
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")
    
    @app.route('/debug-env')
    def debug_env():
        return jsonify({
            "verify_token_from_config": app.config.get('WHATSAPP_VERIFY_TOKEN'),
            "verify_token_from_env": os.getenv('WHATSAPP_VERIFY_TOKEN')
        })
    
    # Main route
    @app.route('/')
    def index():
        user_count = User.query.count()
        expense_count = Expense.query.count()
        
        return jsonify({
            "message": "WhatsApp Receipt Processor is running!",
            "status": "healthy",
            "pos_rate": f"1 TL = {app.config['POS_RATE']} MWK",
            "atm_rate": f"1 TL = {app.config['ATM_RATE']} MWK",
            "database": {
                "users": user_count,
                "expenses": expense_count
            },
            "whatsapp_enabled": whatsapp_service is not None
        })
    

    # Test interface for receipt processing
    @app.route('/test-interface')
    def test_interface():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Receipt Processor - Test Interface</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    max-width: 600px; 
                    margin: 50px auto; 
                    padding: 20px; 
                    background-color: #f0f0f0;
                }
                .container { 
                    background: white; 
                    padding: 30px; 
                    border-radius: 15px; 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                h2 { color: #25D366; text-align: center; }
                .info-box {
                    background: #e8f5e8;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                    border-left: 4px solid #25D366;
                }
                input[type="file"] { 
                    margin: 15px 0; 
                    padding: 10px;
                    border: 2px dashed #ccc;
                    border-radius: 5px;
                    width: 100%;
                }
                button { 
                    background: #25D366; 
                    color: white; 
                    padding: 12px 25px; 
                    border: none; 
                    border-radius: 8px; 
                    font-size: 16px;
                    cursor: pointer;
                    width: 100%;
                }
                button:hover { background: #1fb854; }
                .result { 
                    margin-top: 20px; 
                    padding: 20px; 
                    background: #f9f9f9; 
                    border-radius: 8px;
                    border: 1px solid #ddd;
                }
                .loading {
                    text-align: center;
                    color: #666;
                }
                pre {
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🤖 Receipt Processor Test Interface</h2>
                
                <div class="info-box">
                    <strong>Exchange Rates:</strong><br>
                    🏪 POS Rate: 1 TL = 51.00 MWK<br>
                    🏧 ATM Rate: 1 TL = 54.00 MWK
                </div>
                
                <p>Upload a Turkish receipt to test the processing system:</p>
                
                <form id="receiptForm" enctype="multipart/form-data">
                    <input type="file" id="receipt" name="receipt" accept="image/*" required>
                    <button type="submit">📸 Process Receipt</button>
                </form>
                
                <div id="result" class="result" style="display:none;">
                    <h3>Processing Result:</h3>
                    <div id="resultContent"></div>
                </div>
            </div>
            
            <script>
                document.getElementById('receiptForm').addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const formData = new FormData();
                    const fileInput = document.getElementById('receipt');
                    
                    if (!fileInput.files[0]) {
                        alert('Please select a file first!');
                        return;
                    }
                    
                    formData.append('receipt', fileInput.files[0]);
                    
                    document.getElementById('result').style.display = 'block';
                    document.getElementById('resultContent').innerHTML = 
                        '<div class="loading">📄 Processing receipt...</div>';
                    
                    fetch('/process-receipt', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('resultContent').innerHTML = 
                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    })
                    .catch(error => {
                        document.getElementById('resultContent').innerHTML = 
                            '<p style="color: red;">❌ Error: ' + error + '</p>';
                    });
                });
            </script>
        </body>
        </html>
        '''
    
    # Process receipt (placeholder for now)
    @app.route('/process-receipt', methods=['POST'])
    def process_receipt():
        """Process receipt using OCR"""
        if 'receipt' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        file = request.files['receipt']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        try:
            # Read image data
            image_data = file.read()
            
            # Extract text using OCR
            ocr_result = ocr_service.extract_text_from_image(image_data)
            
            if not ocr_result['success']:
                return jsonify({
                    "status": "error",
                    "message": f"OCR failed: {ocr_result['error']}",
                    "ocr_result": ocr_result
                }), 400
            
            # For now, return the OCR result (tomorrow we'll add LLM processing)
            return jsonify({
                "status": "success",
                "message": "Receipt processed successfully!",
                "ocr_result": {
                    "text": ocr_result['text'],
                    "confidence": ocr_result['confidence'],
                    "word_count": ocr_result.get('word_count', 0)
                },
                "next_step": "LLM processing will be added tomorrow to extract structured data"
            })
            
        except Exception as e:
            logger.error(f"Receipt processing failed: {e}")
            return jsonify({
                "status": "error",
                "message": f"Processing failed: {str(e)}"
            }), 500
    # Test WhatsApp message sending
    @app.route('/test-message/<phone_number>')
    def test_message(phone_number):
        if not whatsapp_service:
            return jsonify({
                "status": "error", 
                "message": "WhatsApp service not available. Please configure credentials."
            }), 500
            
        try:
            result = whatsapp_service.send_message(
                phone_number,
                "🤖 Test message! Bot is working! ✅"
            )
            return jsonify({"status": "sent", "result": result})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # Health check
    @app.route('/health')
    def health():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "connected" if db else "disconnected",
                "whatsapp": "connected" if whatsapp_service else "not configured"
            }
        }), 200
    
    # Database test routes
    @app.route('/test-db')
    def test_database():
        try:
            # Try to create a test user
            test_user = User(
                whatsapp_id=f"test_user_{datetime.now().timestamp()}", 
                phone_number="+1234567890"
            )
            db.session.add(test_user)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "Database test passed",
                "user_id": test_user.id,
                "created_at": test_user.created_at.isoformat()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "status": "error", 
                "message": f"Database test failed: {str(e)}"
            }), 500
    
    @app.route('/test-expense')
    def test_expense():
        try:
            # Get or create test user
            user = DatabaseService.get_or_create_user("test_whatsapp_123")
            
            # Create test expense
            expense_data = {
                'merchant': 'Test Market',
                'amount_tl': 50.75,
                'amount_mwk': 50.75 * 51.00,  # Using POS rate
                'rate_type': 'POS',
                'rate_used': 51.00,
                'expense_date': datetime.now().date(),
                'month_year': datetime.now().strftime('%Y-%m'),
                'items': [
                    {'name': 'Test Item 1', 'price': 25.00},
                    {'name': 'Test Item 2', 'price': 25.75}
                ],
                'confidence': 'high'
            }
            
            expense = DatabaseService.save_expense(user.id, expense_data)
            
            # Get monthly total
            monthly_total = DatabaseService.get_monthly_total(
                user.id, 
                datetime.now().strftime('%Y-%m')
            )
            
            return jsonify({
                "status": "success",
                "expense_id": expense.id,
                "expense_data": {
                    "merchant": expense.merchant,
                    "amount_tl": expense.amount_tl,
                    "amount_mwk": expense.amount_mwk,
                    "rate_type": expense.rate_type,
                    "items": expense.get_items()
                },
                "monthly_total": monthly_total
            })
            
        except Exception as e:
            return jsonify({
                "status": "error", 
                "message": f"Expense test failed: {str(e)}"
            }), 500
    
    # View all expenses (for debugging)
    @app.route('/expenses')
    def view_expenses():
        try:
            expenses = Expense.query.all()
            expense_list = []
            
            for expense in expenses:
                expense_list.append({
                    "id": expense.id,
                    "merchant": expense.merchant,
                    "amount_tl": expense.amount_tl,
                    "amount_mwk": expense.amount_mwk,
                    "rate_type": expense.rate_type,
                    "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
                    "created_at": expense.created_at.isoformat()
                })
            
            return jsonify({
                "status": "success",
                "total_expenses": len(expense_list),
                "expenses": expense_list
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)