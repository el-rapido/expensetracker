from models import db, User, Expense
from datetime import datetime
from sqlalchemy import func

class DatabaseService:
    
    @staticmethod
    def get_or_create_user(whatsapp_id, phone_number=None):
        """Get existing user or create new one"""
        user = User.query.filter_by(whatsapp_id=whatsapp_id).first()
        
        if not user:
            user = User(whatsapp_id=whatsapp_id, phone_number=phone_number)
            db.session.add(user)
            db.session.commit()
        
        return user
    
    @staticmethod
    def save_expense(user_id, expense_data):
        """Save a new expense"""
        expense = Expense(
            user_id=user_id,
            merchant=expense_data.get('merchant'),
            amount_tl=expense_data.get('amount_tl'),
            amount_mwk=expense_data.get('amount_mwk'),
            rate_type=expense_data.get('rate_type'),
            rate_used=expense_data.get('rate_used'),
            expense_date=expense_data.get('expense_date'),
            month_year=expense_data.get('month_year'),
            confidence_level=expense_data.get('confidence', 'medium')
        )
        
        if expense_data.get('items'):
            expense.set_items(expense_data['items'])
        
        db.session.add(expense)
        db.session.commit()
        
        return expense
    
    @staticmethod
    def get_monthly_total(user_id, month_year):
        """Get monthly total for user"""
        total_mwk = db.session.query(func.sum(Expense.amount_mwk)).filter(
            Expense.user_id == user_id,
            Expense.month_year == month_year
        ).scalar() or 0
        
        total_tl = db.session.query(func.sum(Expense.amount_tl)).filter(
            Expense.user_id == user_id,
            Expense.month_year == month_year
        ).scalar() or 0
        
        count = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.month_year == month_year
        ).count()
        
        return {
            'mwk_total': round(total_mwk, 2),
            'tl_total': round(total_tl, 2),
            'transaction_count': count
        }