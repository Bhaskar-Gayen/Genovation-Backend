from celery import Celery
from app.config import settings
import logging




celery_app = Celery(
    "llm_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.llm_tasks"]

)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.llm_tasks.*": {"queue": "llm"},
    },
    task_default_retry_delay=10,
    task_max_retries=3,
    worker_max_tasks_per_child=100,
    broker_transport_options={"visibility_timeout": 3600},
)
celery_app.conf.broker_connection_retry_on_startup = True

celery_app.autodiscover_tasks(['app.workers.llm_tasks'])

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# celery -A celery_app worker -Q llm --loglevel=info to run celery MQ