import os
import redis
import requests
import logging
import time
import json
import socket
import uuid
import traceback
from dotenv import load_dotenv
import schedule
from pythonjsonlogger import jsonlogger
# Load environment variables from .env file
load_dotenv()

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = socket.gethostname()
        self.pod_name = os.getenv('POD_NAME', self.hostname)
        self.namespace = os.getenv('POD_NAMESPACE', 'default')
        self.service_name = os.getenv('SERVICE_NAME', 'telegram-service')
        self.app_version = os.getenv('APP_VERSION', '1.0.0')

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.update({
            'timestamp': record.created,
            'level': record.levelname,
            'logger': record.name,
            'service': self.service_name,
            'hostname': self.hostname,
            'pod': self.pod_name,
            'namespace': self.namespace,
            'version': self.app_version,
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
        })
        if record.exc_info:
            log_record['exception'] = traceback.format_exception(*record.exc_info)
        if trace_id := getattr(record, 'trace_id', None):
            log_record['trace_id'] = trace_id

class RequestContextFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.trace_id = str(uuid.uuid4())

    def filter(self, record):
        record.trace_id = getattr(record, 'trace_id', self.trace_id)
        return True

def setup_logging():
    level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logger = logging.getLogger()
    logger.setLevel(level)
    
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    
    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s [%(service)s] [%(trace_id)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logger.addFilter(RequestContextFilter())
    for name in ('requests', 'urllib3', 'schedule'):
        logging.getLogger(name).setLevel(logging.WARNING)
    
    return logger

# Connect to Redis
logger = setup_logging()
try:
    r = redis.Redis(
        host=os.environ.get('REDIS_HOST'),
        port=int(os.environ.get('REDIS_PORT')),
        db=int(os.environ.get('REDIS_DB', 0)),
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )
    r.ping()
    logger.info("Redis connection established", 
                extra={'component': 'redis', 'operation': 'connect'})
except Exception as e:
    logger.error("Redis connection failed",
                 extra={'component': 'redis', 'error': str(e)},
                 exc_info=True)
    raise

# Get required variables from environment
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')
TG_FILM_BOT_TOKEN = os.environ.get('TG_FILM_BOT_TOKEN')

if not TG_CHAT_ID or not TG_FILM_BOT_TOKEN:
    logging.error("Environment variables TG_CHAT_ID or TG_FILM_BOT_TOKEN are not set")
    exit(1)

def publish_poster(movie_id, jpg, vote_average):
    """Publish the poster image to Telegram."""
    url = f"https://api.telegram.org/bot{TG_FILM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TG_CHAT_ID,
        "caption": f"TMDB: {vote_average}",
        "parse_mode": "HTML"
    }
    
    extra = {
        'component': 'telegram',
        'movie_id': movie_id,
        'file': jpg,
        'operation': 'send_photo'
    }
    
    try:
        os.makedirs("jpgs", exist_ok=True)
        with open(f"jpgs/{jpg}", "rb") as photo:
            response = requests.post(url, data=payload, files={"photo": photo}, timeout=10)
            
        if response.status_code == 200:
            logger.info("Poster published successfully",
                       extra={**extra, 'status': 'success', 'http_status': 200})
            return True
            
        logger.error("Failed to publish poster",
                    extra={**extra, 'status': 'error',
                           'http_status': response.status_code,
                           'response': response.text[:200]})
        return False
    except Exception as e:
        logger.error("Exception publishing poster",
                    extra={**extra, 'error': str(e)},
                    exc_info=True)
        return False


def process_posters():
    """Process posters queue from Redis."""
    trace_id = str(uuid.uuid4())
    extra = {
        'component': 'processor',
        'operation': 'process_queue',
        'trace_id': trace_id
    }
    
    try:
        logger.info("Starting posters processing", extra=extra)
        all_poster_keys = r.keys(b"poster:*")
        logger.info("Found poster keys",
                   extra={**extra, 'key_count': len(all_poster_keys)})

        for key in all_poster_keys:
            key_str = key.decode('utf-8')
            movie_id = key_str.split(':')[1]

            poster_data = r.hgetall(key)
            status = poster_data.get(b'status', b'').decode('utf-8')
            movie_extra = {**extra, 'movie_id': movie_id}

            if status == "published":
                logger.debug("Skipping published poster", 
                            extra={**movie_extra, 'status': 'skipped'})
                continue

            jpg = poster_data.get(b'jpg', b'').decode('utf-8')
            vote_average = poster_data.get(b'vote_average', b'').decode('utf-8')

            if publish_poster(movie_id, jpg, vote_average):
                r.hset(key, "status", "published")
                logger.info("Poster status updated",
                            extra={**movie_extra, 'new_status': 'published'})
            else:
                logger.warning("Poster publication failed",
                              extra={**movie_extra, 'retry': True})
    
    except Exception as e:
        logger.error("Poster processing failed",
                    extra={**extra, 'error': str(e)},
                    exc_info=True)


if __name__ == "__main__":
    # In a production environment you might want to wrap this in a loop
    # or use a scheduler to run periodically.
    process_posters()
    # main_job()
    
    # Планируем запуск основного задания каждые 40 секунд
    schedule.every(40).seconds.do(process_posters)
    while True:
        schedule.run_pending()
        time.sleep(1)
