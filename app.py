from flask import Flask, request, jsonify
from config import Config
from models import db, User, Expense
from services.database_service import DatabaseService
from services.whatsapp_service import WhatsAppService
from services.exchange_rate_service import ExchangeRateService
from services.receipt_workflow import ReceiptWorkflow
from services.message_handler import MessageHandler
from services.llm_service import LLMService
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
    llm_service = LLMService(app.config.get('GEMINI_API_KEY'))
    
   # Initialize WhatsApp service (only if credentials are available)
    whatsapp_service = None
    message_handler = None
    

    exchange_rate_service = ExchangeRateService(
            app.config['POS_RATE'], 
            app.config['ATM_RATE']
        )    
   #Initialize OCR Service
    ocr_service = OCRService()
    llm_service = LLMService(app.config.get('GEMINI_API_KEY'))

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
    
    @app.route('/test-ocr-debug')
    def test_ocr_debug():
        """Debug OCR service initialization"""
        try:
            import os
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            debug_info = {
                "credentials_env_var": credentials_path,
                "credentials_file_exists": os.path.exists(credentials_path) if credentials_path else False,
                "ocr_service_available": hasattr(ocr_service, 'client') and ocr_service.client is not None
            }
            
            if hasattr(ocr_service, 'client') and ocr_service.client is not None:
                # Try a simple OCR test
                test_result = ocr_service.extract_text_from_image(b"dummy")
                debug_info["test_ocr_result"] = test_result
            
            return jsonify(debug_info)
            
        except Exception as e:
            return jsonify({
                "error": str(e),
                "type": type(e).__name__
            })
    @app.route('/test-path-debug')
    def test_path_debug():
        import os
        current_dir = os.getcwd()
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        full_path = os.path.join(current_dir, credentials_path) if credentials_path else None
        
        return jsonify({
            "current_working_directory": current_dir,
            "credentials_env_var": credentials_path,
            "full_credentials_path": full_path,
            "full_path_exists": os.path.exists(full_path) if full_path else False,
            "files_in_current_dir": os.listdir(current_dir)
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
    
    @app.route('/select-rate', methods=['POST'])
    def select_rate():
        """Handle rate selection and complete receipt processing"""
        
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            
            required_fields = ['extracted_data', 'rate_type', 'user_id']
            for field in required_fields:
                if field not in data:
                    return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400
            
            # Get the data
            extracted_data = data['extracted_data']
            rate_type = data['rate_type'].upper()
            user_whatsapp_id = data['user_id']
            
            # Step 1: Get or create user
            user = DatabaseService.get_or_create_user(user_whatsapp_id)
            
            # Step 2: Calculate currency conversion
            tl_amount = extracted_data['total_amount']
            
            if rate_type == 'POS':
                rate_used = app.config['POS_RATE']
            elif rate_type == 'ATM':
                rate_used = app.config['ATM_RATE']
            else:
                return jsonify({"status": "error", "message": "Invalid rate type"}), 400
            
            mwk_amount = tl_amount * rate_used
            
            # Step 3: Prepare expense data
            expense_date = datetime.strptime(extracted_data['date'], '%Y-%m-%d').date()
            month_year = expense_date.strftime('%Y-%m')
            
            expense_data = {
                'merchant': extracted_data['merchant_name'],
                'amount_tl': round(tl_amount, 2),
                'amount_mwk': round(mwk_amount, 2),
                'rate_type': rate_type,
                'rate_used': rate_used,
                'expense_date': expense_date,
                'month_year': month_year,
                'items': extracted_data.get('items', []),
                'confidence': extracted_data.get('confidence', 'medium'),
                'receipt_number': extracted_data.get('receipt_number'),
                'tax_amount': extracted_data.get('tax_amount', 0)
            }
            
            # Step 4: Save to database
            expense = DatabaseService.save_expense(user.id, expense_data)
            
            # Step 5: Get updated monthly total
            monthly_total = DatabaseService.get_monthly_total(user.id, month_year)
            
            # Step 6: Create success message
            success_message = f"""✅ Receipt Saved Successfully!

    **This Purchase:**
    🏪 {expense_data['merchant']}
    💰 ₺{expense_data['amount_tl']:.2f} → {expense_data['amount_mwk']:.2f} MWK
    📊 Rate: {expense_data['rate_type']} ({expense_data['rate_used']:.2f})
    📅 Date: {expense_data['expense_date']}

    **Monthly Summary ({expense_data['month_year']}):**
    💵 {monthly_total['mwk_total']:.2f} MWK total
    ₺ {monthly_total['tl_total']:.2f} TL total
    🧾 {monthly_total['transaction_count']} transactions

    Use "total" command to see current month anytime."""
            
            return jsonify({
                "status": "success",
                "message": success_message,
                "expense_id": expense.id,
                "monthly_total": monthly_total,
                "expense_data": {
                    "merchant": expense_data['merchant'],
                    "amount_tl": expense_data['amount_tl'],
                    "amount_mwk": expense_data['amount_mwk'],
                    "rate_type": expense_data['rate_type']
                }
            })
            
        except Exception as e:
            logger.error(f"Rate selection failed: {e}")
            return jsonify({
                "status": "error",
                "message": f"Processing failed: {str(e)}"
            }), 500


   
    # Test interface for receipt processing
    
    @app.route('/test-interface')
    def test_interface():
        return '''<!DOCTYPE html>
    <html>
    <head>
        <title>Receipt Processor</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #f0f0f0; }
            .container { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h2 { color: #25D366; text-align: center; }
            .info-box { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0; }
            input[type="file"] { margin: 15px 0; padding: 10px; width: 90%; }
            .btn { background: #25D366; color: white; padding: 12px 25px; border: none; border-radius: 8px; cursor: pointer; margin: 5px; }
            .result { margin-top: 20px; padding: 20px; background: #f9f9f9; border-radius: 8px; }
            .rate-btn { background: #28a745; width: 45%; display: inline-block; }
            .atm-btn { background: #007bff; }
            pre { background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🤖 Receipt Processor Test</h2>
            
            <div class="info-box">
                <strong>Exchange Rates:</strong><br>
                🏪 POS Rate: 1 TL = 51.00 MWK<br>
                🏧 ATM Rate: 1 TL = 54.00 MWK
            </div>
            
            <div>
                <input type="file" id="fileInput" accept="image/*" required>
                <button class="btn" onclick="processReceipt()">📸 Process Receipt</button>
            </div>
            
            <div id="result" class="result" style="display:none;">
                <div id="content"></div>
            </div>
        </div>

    <script>
    let receiptData = null;

    function processReceipt() {
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        
        if (!file) {
            alert('Please select a file first!');
            return;
        }
        
        const formData = new FormData();
        formData.append('receipt', file);
        
        document.getElementById('result').style.display = 'block';
        document.getElementById('content').innerHTML = '<p>📄 Processing receipt...</p>';
        
        fetch('/process-receipt', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log('Response:', data);
            
            if (data.status === 'success' && data.stage === 'rate_selection') {
                receiptData = data;
                showRateButtons(data);
            } else {
                document.getElementById('content').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('content').innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
        });
    }

    function showRateButtons(data) {
        const merchant = data.extracted_data.merchant_name;
        const amount = data.extracted_data.total_amount;
        const posAmount = data.rate_selection.pos_conversion.mwk_amount;
        const atmAmount = data.rate_selection.atm_conversion.mwk_amount;
        
        document.getElementById('content').innerHTML = `
            <h3>📋 Receipt Processed Successfully!</h3>
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #ddd;">
                <strong>🏪 ${merchant}</strong><br>
                <strong>💰 ₺${amount}</strong><br>
                <strong>📅 ${data.extracted_data.date}</strong>
            </div>
            <h4>💱 Choose Exchange Rate:</h4>
            <button class="btn rate-btn" onclick="saveReceipt('POS')">
                🏪 POS Rate<br>
                <small>${posAmount.toFixed(2)} MWK</small>
            </button>
            <button class="btn rate-btn atm-btn" onclick="saveReceipt('ATM')">
                🏧 ATM Rate<br>
                <small>${atmAmount.toFixed(2)} MWK</small>
            </button>
        `;
    }

    function saveReceipt(rateType) {
        document.getElementById('content').innerHTML = '<p>💾 Saving receipt to database...</p>';
        
        fetch('/select-rate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                extracted_data: receiptData.extracted_data,
                rate_type: rateType,
                user_id: 'test_user_web_interface'
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Save response:', data);
            
            if (data.status === 'success') {
                document.getElementById('content').innerHTML = `
                    <div style="background: #d4edda; padding: 20px; border-radius: 10px; border: 1px solid #c3e6cb;">
                        <h3>✅ Receipt Saved Successfully!</h3>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: monospace;">
    ${data.message}
                        </div>
                        <br>
                        <button class="btn" onclick="location.reload()">🔄 Process Another Receipt</button>
                    </div>
                `;
            } else {
                document.getElementById('content').innerHTML = '<pre style="color: red;">' + JSON.stringify(data, null, 2) + '</pre>';
            }
        })
        .catch(error => {
            console.error('Save error:', error);
            document.getElementById('content').innerHTML = '<p style="color: red;">Error saving: ' + error.message + '</p>';
        });
    }
    </script>
    </body>
    </html>'''
    
  
    
    

    # Process receipt 
    
    @app.route('/process-receipt', methods=['POST'])
    def process_receipt():
        """Process receipt using OCR + LLM + Rate Selection"""
        if 'receipt' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        file = request.files['receipt']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        try:
            # Step 1: Extract text using OCR
            image_data = file.read()
            ocr_result = ocr_service.extract_text_from_image(image_data)
            
            if not ocr_result['success']:
                return jsonify({
                    "status": "error",
                    "message": f"OCR failed: {ocr_result['error']}",
                    "step": "ocr"
                }), 400
            
            # Step 2: Process text using LLM
            llm_result = llm_service.process_receipt_text(ocr_result['text'])
            
            if not llm_result['success']:
                return jsonify({
                    "status": "error",
                    "message": f"LLM processing failed: {llm_result['error']}",
                    "step": "llm",
                    "ocr_text": ocr_result['text']
                }), 400
            
            # Step 3: Create rate selection options
            rate_selection = exchange_rate_service.create_rate_selection_message(
                llm_result['data']
            )
            
            # Step 4: Return everything for user confirmation
            return jsonify({
                "status": "success",
                "message": "Receipt processed successfully!",
                "stage": "rate_selection",
                "ocr_confidence": ocr_result['confidence'],
                "llm_confidence": llm_result['data']['confidence'],
                "raw_text": ocr_result['text'],
                "extracted_data": llm_result['data'],
                "rate_selection": rate_selection,
                "next_action": "User needs to select POS or ATM rate"
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