import logging
from services.whatsapp_service import WhatsAppService
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, whatsapp_service):
        self.whatsapp = whatsapp_service
    
    def handle_incoming_message(self, webhook_data):
        """Process incoming WhatsApp messages"""
        try:
            # Extract message data
            entry = webhook_data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            messages = value.get('messages', [])
            
            for message in messages:
                self.process_message(message)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def process_message(self, message):
        """Process individual message"""
        message_type = message.get('type')
        from_number = message.get('from')
        message_id = message.get('id')
        
        # Mark as read
        self.whatsapp.mark_as_read(message_id)
        
        # Get or create user
        user = DatabaseService.get_or_create_user(from_number)
        
        if message_type == 'text':
            self.handle_text_message(message, from_number, user)
        elif message_type == 'image':
            self.handle_image_message(message, from_number, user)
        elif message_type == 'interactive':
            self.handle_interactive_message(message, from_number, user)
        else:
            self.send_help_message(from_number)
    
    def handle_text_message(self, message, from_number, user):
        """Handle text messages"""
        text = message.get('text', {}).get('body', '').lower().strip()
        
        if text in ['hi', 'hello', 'hey', 'start']:
            self.send_welcome_message(from_number)
        elif text in ['help', 'info']:
            self.send_help_message(from_number)
        elif text in ['total', 'balance', 'summary']:
            self.send_monthly_total(from_number, user.id)
        else:
            self.send_help_message(from_number)
    
    def handle_image_message(self, message, from_number, user):
        """Handle receipt images"""
        media_id = message.get('image', {}).get('id')
        
        if media_id:
            # For now, just acknowledge receipt
            self.whatsapp.send_message(
                from_number,
                "📄 Receipt received! Processing...\n\n(OCR feature will be added tomorrow)"
            )
        else:
            self.whatsapp.send_message(
                from_number,
                "❌ Could not receive image. Please try again."
            )
    
    def handle_interactive_message(self, message, from_number, user):
        """Handle button clicks"""
        button_reply = message.get('interactive', {}).get('button_reply', {})
        button_id = button_reply.get('id')
        
        if button_id == 'pos_rate':
            self.whatsapp.send_message(from_number, "✅ POS rate selected!")
        elif button_id == 'atm_rate':
            self.whatsapp.send_message(from_number, "✅ ATM rate selected!")
        else:
            self.send_help_message(from_number)
    
    def send_welcome_message(self, to_number):
        """Send welcome message"""
        message = """🤖 **Welcome to Receipt Processor Bot!**

This bot processes your Turkish receipts and tracks your monthly expenses in MWK.

**How to use:**
📸 Send a photo of your receipt
✅ Confirm the extracted information  
💱 Choose rate type (POS/ATM)
📊 View your monthly total

**Commands:**
- "total" - Current month total
- "help" - Show help

Let's get started! 🚀"""

        self.whatsapp.send_message(to_number, message)
    
    def send_help_message(self, to_number):
        """Send help message"""
        message = """📋 **Help**

**Sending Receipts:**
1. Take a clear photo of your receipt
2. Send it to this bot via WhatsApp
3. Review the extracted information
4. Choose rate type (POS/ATM)

**Commands:**
- "total" or "summary" - Monthly total
- "hello" or "hi" - Welcome message

**Having issues?** Make sure your receipt photo is clear and straight."""

        self.whatsapp.send_message(to_number, message)
    
    def send_monthly_total(self, to_number, user_id):
        """Send current month total"""
        from datetime import datetime
        
        current_month = datetime.now().strftime('%Y-%m')
        totals = DatabaseService.get_monthly_total(user_id, current_month)
        
        message = f"""📊 **This Month's Total**

💰 **₺{totals['tl_total']:.2f}** → **{totals['mwk_total']:.2f} MWK**
🧾 **{totals['transaction_count']} transactions**

_Monthly summary is sent automatically on the 1st of each month._"""

        self.whatsapp.send_message(to_number, message)