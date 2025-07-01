import logging
from datetime import datetime
from services.database_service import DatabaseService
from services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)

class ReceiptWorkflow:
    def __init__(self, exchange_rate_service):
        self.exchange_rate_service = exchange_rate_service
    
    def process_complete_receipt(self, user_whatsapp_id, extracted_data, rate_type):
        """Complete receipt processing workflow"""
        
        try:
            # Step 1: Get or create user
            user = DatabaseService.get_or_create_user(user_whatsapp_id)
            
            # Step 2: Calculate currency conversion
            conversion = self.exchange_rate_service.calculate_conversion(
                extracted_data['total_amount'], 
                rate_type
            )
            
            # Step 3: Prepare expense data
            expense_date = datetime.strptime(extracted_data['date'], '%Y-%m-%d').date()
            month_year = expense_date.strftime('%Y-%m')
            
            expense_data = {
                'merchant': extracted_data['merchant_name'],
                'amount_tl': conversion['tl_amount'],
                'amount_mwk': conversion['mwk_amount'],
                'rate_type': conversion['rate_type'],
                'rate_used': conversion['rate_used'],
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
            success_message = self.create_success_message(
                expense_data, monthly_total, extracted_data
            )
            
            return {
                "success": True,
                "expense_id": expense.id,
                "expense_data": expense_data,
                "monthly_total": monthly_total,
                "message": success_message
            }
            
        except Exception as e:
            logger.error(f"Receipt workflow failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to save receipt: {str(e)}"
            }
    
    def create_success_message(self, expense_data, monthly_total, original_data):
        """Create success confirmation message"""
        
        message = f"""✅ **Receipt Saved Successfully!**

**This Purchase:**
🏪 **{expense_data['merchant']}**
💰 **₺{expense_data['amount_tl']:.2f}** → **{expense_data['amount_mwk']:.2f} MWK**
📊 **Rate:** {expense_data['rate_type']} ({expense_data['rate_used']:.2f})
📅 **Date:** {expense_data['expense_date']}

**Monthly Summary ({expense_data['month_year']}):**
💵 **{monthly_total['mwk_total']:.2f} MWK** total
₺ **{monthly_total['tl_total']:.2f} TL** total
🧾 **{monthly_total['transaction_count']} transactions**

_Use "total" command to see current month anytime._"""

        return message