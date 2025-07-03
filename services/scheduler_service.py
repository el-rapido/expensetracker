import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, monthly_tracking_service):
        self.monthly_tracking_service = monthly_tracking_service
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Scheduler service started")
    
    def setup_monthly_summaries(self):
        """Set up monthly summary automation"""
        
        # Schedule for 1st of each month at 9:00 AM
        self.scheduler.add_job(
            func=self.monthly_tracking_service.send_monthly_summaries,
            trigger=CronTrigger(day=1, hour=9, minute=0),
            id='monthly_summaries',
            name='Send Monthly Summaries',
            replace_existing=True
        )
        
        logger.info("Monthly summary automation scheduled for 1st of each month at 9:00 AM")
    
    def setup_test_schedule(self):
        """Set up test schedule (every 5 minutes for testing)"""
        
        self.scheduler.add_job(
            func=self.test_monthly_job,
            trigger=CronTrigger(minute='*/5'),
            id='test_monthly',
            name='Test Monthly Job',
            replace_existing=True
        )
        
        logger.info("Test monthly job scheduled every 5 minutes")
    
    def test_monthly_job(self):
        """Test version of monthly job"""
        logger.info("Test monthly job executed!")
        
        # You can test the monthly summary logic here
        # result = self.monthly_tracking_service.send_monthly_summaries()
        # logger.info(f"Test monthly job result: {result}")
    
    def get_scheduled_jobs(self):
        """Get list of scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler service stopped")