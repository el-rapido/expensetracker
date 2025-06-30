from flask import Flask, request, jsonify
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Basic route to test everything works
    @app.route('/')
    def index():
        return jsonify({
            "message": "WhatsApp Receipt Processor is running!",
            "status": "healthy",
            "pos_rate": app.config['POS_RATE'],
            "atm_rate": app.config['ATM_RATE']
        })
    
    # WhatsApp webhook verification (we'll implement this properly tomorrow)
    @app.route('/webhook', methods=['GET', 'POST'])
    def whatsapp_webhook():
        if request.method == 'GET':
            # Webhook verification
            verify_token = request.args.get('hub.verify_token')
            if verify_token == app.config['WHATSAPP_VERIFY_TOKEN']:
                return request.args.get('hub.challenge')
            return 'Verification failed', 403
        
        elif request.method == 'POST':
            # Handle incoming messages (placeholder for now)
            logger.info("Received WhatsApp message")
            return jsonify({"status": "received"}), 200
    
    # Health check route
    @app.route('/health')
    def health():
        return jsonify({"status": "healthy"}), 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)