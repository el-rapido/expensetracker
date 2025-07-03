import logging
from datetime import datetime, date
from calendar import monthrange
from services.database_service import DatabaseService
from services.sms_service import SMSService
from models import User, Expense
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)

class MonthlyTrackingService:
    def __init__(self, sms_service):
        self.sms_service = sms_service
    
    def get_enhanced_monthly_summary(self, user_id, month_year):
        """Get detailed monthly summary with analytics"""
        
        # Get basic totals
        basic_summary = DatabaseService.get_monthly_total(user_id, month_year)
        
        # Get expenses for the month
        expenses = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.month_year == month_year
        ).all()
        
        if not expenses:
            return basic_summary
        
        # Calculate additional analytics
        enhanced_summary = basic_summary.copy()
        
        # Top merchants
        merchant_totals = {}
        rate_breakdown = {'POS': 0, 'ATM': 0}
        daily_spending = {}
        
        for expense in expenses:
            # Merchant analysis
            merchant = expense.merchant or 'Unknown'
            merchant_totals[merchant] = merchant_totals.get(merchant, 0) + expense.amount_mwk
            
            # Rate analysis
            rate_breakdown[expense.rate_type] = rate_breakdown.get(expense.rate_type, 0) + expense.amount_mwk
            
            # Daily spending
            day = expense.expense_date.day
            daily_spending[day] = daily_spending.get(day, 0) + expense.amount_mwk
        
        # Top 3 merchants
        top_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Average transaction
        avg_transaction = basic_summary['mwk_total'] / basic_summary['transaction_count'] if basic_summary['transaction_count'] > 0 else 0
        
        # Highest spending day
        highest_day = max(daily_spending.items(), key=lambda x: x[1]) if daily_spending else (0, 0)
        
        enhanced_summary.update({
            'top_merchants': top_merchants,
            'top_merchant': top_merchants[0][0] if top_merchants else 'N/A',
            'rate_breakdown': rate_breakdown,
            'average_transaction': round(avg_transaction, 2),
            'highest_spending_day': highest_day[0],
            'highest_spending_amount': round(highest_day[1], 2),
            'month_year': month_year
        })
        
        return enhanced_summary
    
    def generate_monthly_report(self, user_id, month_year):
        """Generate detailed monthly report"""
        
        summary = self.get_enhanced_monthly_summary(user_id, month_year)
        
        if summary['transaction_count'] == 0:
            return "📊 No transactions found for this month."
        
        # Format detailed report
        report = f"""📊 **{month_year} Monthly Report**

**💰 TOTALS:**
- Turkish Lira: ₺{summary['tl_total']:.2f}
- Malawi Kwacha: {summary['mwk_total']:.2f} MWK
- Transactions: {summary['transaction_count']}
- Average per transaction: {summary['average_transaction']:.2f} MWK

**🏪 TOP MERCHANTS:**"""
        
        for i, (merchant, amount) in enumerate(summary['top_merchants'], 1):
            report += f"\n{i}. {merchant}: {amount:.2f} MWK"
        
        report += f"""

**💳 PAYMENT METHODS:**
- POS Transactions: {summary['rate_breakdown'].get('POS', 0):.2f} MWK
- ATM Transactions: {summary['rate_breakdown'].get('ATM', 0):.2f} MWK

**📈 INSIGHTS:**
- Highest spending day: {summary['highest_spending_day']} ({summary['highest_spending_amount']:.2f} MWK)
- Most frequent merchant: {summary['top_merchant']}

_Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}_"""
        
        return report
    
    def send_monthly_summaries(self):
        """Send monthly summaries to all users (run on 1st of month)"""
        
        # Get previous month
        today = date.today()
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        
        prev_month_year = f"{prev_year}-{prev_month:02d}"
        
        logger.info(f"Sending monthly summaries for {prev_month_year}")
        
        # Get all users with transactions in previous month
        users_with_expenses = User.query.join(Expense).filter(
            Expense.month_year == prev_month_year
        ).distinct().all()
        
        sent_count = 0
        error_count = 0
        
        for user in users_with_expenses:
            try:
                # Get enhanced summary
                summary = self.get_enhanced_monthly_summary(user.id, prev_month_year)
                
                if summary['transaction_count'] > 0 and user.phone_number:
                    # Send SMS
                    result = self.sms_service.send_monthly_summary(
                        user.phone_number, 
                        summary
                    )
                    
                    if result['success']:
                        sent_count += 1
                        logger.info(f"Monthly SMS sent to user {user.id}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to send SMS to user {user.id}: {result['error']}")
                        
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing monthly summary for user {user.id}: {e}")
        
        logger.info(f"Monthly summaries complete: {sent_count} sent, {error_count} errors")
        
        return {
            "sent_count": sent_count,
            "error_count": error_count,
            "month_processed": prev_month_year
        }
    
    def get_yearly_summary(self, user_id, year):
        """Get yearly summary for user"""
        
        yearly_data = {
            'year': year,
            'total_mwk': 0,
            'total_tl': 0,
            'total_transactions': 0,
            'monthly_breakdown': [],
            'top_merchants': {},
            'rate_breakdown': {'POS': 0, 'ATM': 0}
        }
        
        for month in range(1, 13):
            month_year = f"{year}-{month:02d}"
            monthly_summary = self.get_enhanced_monthly_summary(user_id, month_year)
            
            yearly_data['total_mwk'] += monthly_summary['mwk_total']
            yearly_data['total_tl'] += monthly_summary['tl_total']
            yearly_data['total_transactions'] += monthly_summary['transaction_count']
            
            yearly_data['monthly_breakdown'].append({
                'month': month,
                'month_name': datetime(year, month, 1).strftime('%B'),
                'mwk_total': monthly_summary['mwk_total'],
                'transaction_count': monthly_summary['transaction_count']
            })
            
            # Aggregate top merchants
            for merchant, amount in monthly_summary.get('top_merchants', []):
                yearly_data['top_merchants'][merchant] = yearly_data['top_merchants'].get(merchant, 0) + amount
            
            # Aggregate rate breakdown
            for rate_type, amount in monthly_summary.get('rate_breakdown', {}).items():
                yearly_data['rate_breakdown'][rate_type] += amount
        
        # Sort top merchants
        yearly_data['top_merchants'] = sorted(
            yearly_data['top_merchants'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return yearly_data