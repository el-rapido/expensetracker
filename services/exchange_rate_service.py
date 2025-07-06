import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ExchangeRateService:
    def __init__(self, pos_rate, atm_rate):
        """Initialize with hardcoded exchange rates"""
        self.pos_rate = pos_rate  # 48.00 MWK per 1 TL
        self.atm_rate = atm_rate  # 54.00 MWK per 1 TL
        logger.info(f"Exchange rates initialized - POS: {pos_rate}, ATM: {atm_rate}")
    
    def get_rates(self):
        """Get current exchange rates"""
        return {
            "pos_rate": self.pos_rate,
            "atm_rate": self.atm_rate,
            "currency_from": "TRY",
            "currency_to": "MWK",
            "last_updated": datetime.now().isoformat()
        }
    
    def calculate_conversion(self, tl_amount, rate_type):
        """Convert TL to MWK using specified rate"""
        
        if rate_type.upper() == 'POS':
            rate = self.pos_rate
        elif rate_type.upper() == 'ATM':
            rate = self.atm_rate
        else:
            raise ValueError(f"Invalid rate type: {rate_type}. Use 'POS' or 'ATM'")
        
        mwk_amount = tl_amount * rate
        
        return {
            "tl_amount": round(tl_amount, 2),
            "mwk_amount": round(mwk_amount, 2),
            "rate_used": rate,
            "rate_type": rate_type.upper(),
            "calculation_date": datetime.now().isoformat()
        }
    
    def create_rate_selection_message(self, receipt_data):
        """Create message for rate selection"""
        
        tl_amount = receipt_data.get('total_amount', 0)
        
        # Calculate both options
        pos_conversion = self.calculate_conversion(tl_amount, 'POS')
        atm_conversion = self.calculate_conversion(tl_amount, 'ATM')
        
        message = f"""💱 *Choose Exchange Rate*

*Receipt:* {receipt_data.get('merchant_name', 'Unknown')}
*Amount:* ₺{tl_amount:.2f}

*Rate Options:*

🏪 *POS Rate* (1 TL = {self.pos_rate} MWK)
   → *{pos_conversion['mwk_amount']:.2f} MWK*

🏧 *ATM Rate* (1 TL = {self.atm_rate} MWK)  
   → *{atm_conversion['mwk_amount']:.2f} MWK*

*Which rate applies to this purchase?*"""

        return {
            "message": message,
            "pos_conversion": pos_conversion,
            "atm_conversion": atm_conversion,
            "receipt_data": receipt_data
        }