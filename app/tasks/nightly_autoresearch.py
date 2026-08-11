import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.agentic.autoresearch import AutoresearchLoop

logger = logging.getLogger("zenu.scheduler")
scheduler = AsyncIOScheduler(timezone="UTC")

@scheduler.scheduled_job("cron", hour=2, minute=0)
def run_nightly_autoresearch():
    logger.info("Nightly Autoresearch job triggered.")
    from app.dependencies import get_supabase_service_client
    sb = get_supabase_service_client()
    AutoresearchLoop(sb).run()
