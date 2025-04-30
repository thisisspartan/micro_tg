import os
import time
import json
import logging
import socket
import uuid
import traceback

import requests
import redis
import schedule
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = socket.gethostname()
        self.pod_name = os.getenv('POD_NAME', self.hostname)
        self.namespace = os.getenv('POD_NAMESPACE', 'default')
        self.service_name = os.getenv('SERVICE_NAME', 'tmdb-service')
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


def setup_logging():
    level = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers:
        root.removeHandler(h)
    console = logging.StreamHandler()
    fmt = '%(timestamp)s %(level)s [%(service)s] [%(trace_id)s] %(message)s'
    console.setFormatter(CustomJsonFormatter(fmt))
    root.addHandler(console)
    for name in ('requests', 'urllib3', 'schedule'):
        logging.getLogger(name).setLevel(logging.WARNING)
    return root


class RequestContextFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.trace_id = str(uuid.uuid4())

    def filter(self, record):
        record.trace_id = getattr(record, 'trace_id', self.trace_id)
        return True



def get_redis_client():
    cfg = {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'db': int(os.getenv('REDIS_DB', 0)),
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
        'retry_on_timeout': True
    }
    client = redis.Redis(**cfg)
    client.ping()
    return client

logger = setup_logging()

# Module-level variables for requests
HEADERS = None
PROXIES = None
redis_client = None

URLS = {
    'movies': f"https://api.themoviedb.org/3/account/{os.getenv('TMDB_ACCOUNT_ID')}/favorite/movies?language=en-US&page=1&sort_by=created_at.asc",
    'tv': f"https://api.themoviedb.org/3/account/{os.getenv('TMDB_ACCOUNT_ID')}/favorite/tv?language=en-US&page=1&sort_by=created_at.asc"
}


def request_json(url, extra):
    resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    logger.info('Retrieved data', extra={**extra, 'items_count': len(data.get('results', []))})
    return data


def extract_movies_tv():
    items = []
    for key, url in URLS.items():
        try:
            items.append(request_json(url, {'component': 'tmdb_api', 'category': key}))
        except Exception as e:
            logger.error('TMDB fetch failed', exc_info=True,
                         extra={'component': 'tmdb_api', 'category': key, 'error': str(e)})
    return items


def extract_jpg_paths(id_dict):
    posters = {}
    templates = {
        'movie': "https://api.themoviedb.org/3/movie/{}/images?language=ru",
        'tv': "https://api.themoviedb.org/3/tv/{}/images?language=ru"
    }
    for mid, meta in id_dict.items():
        for cat, tmpl in templates.items():
            try:
                data = request_json(tmpl.format(mid), {'component': 'tmdb_api', 'movie_id': mid, 'category': cat})
                if not data.get('success') and data.get('posters'):
                    posters[mid] = [data['posters'][0].get('file_path'), meta]
                    break
            except Exception:
                continue
    return posters


def download_posters(posters):
    os.makedirs('jpgs', exist_ok=True)
    for mid, (path, _) in posters.items():
        url = f"https://image.tmdb.org/t/p/w500{path}"
        resp = requests.get(url, proxies=PROXIES, timeout=30)
        resp.raise_for_status()
        filename = path.lstrip('/').replace('/', '')
        with open(os.path.join('jpgs', filename), 'wb') as f:
            f.write(resp.content)
        logger.info('Poster saved', extra={'component': 'downloader', 'movie_id': mid, 'file': filename})


def group_ids(data_list):
    result = {}
    def recurse(data):
        if isinstance(data, dict):
            if (pk := data.get('id')):
                result.setdefault(pk, []).append(data)
            for v in data.values(): recurse(v)
        elif isinstance(data, list):
            for i in data: recurse(i)
    recurse(data_list)
    return {k: [d.get('vote_average') for d in v] for k, v in result.items()}


def push_to_redis(posters):
    for mid, (path, meta) in posters.items():
        key = f"poster:{mid}"
        if not redis_client.exists(key):
            redis_client.hset(key, mapping={'jpg': path.lstrip('/'), 'vote_average': str(meta[0]), 'status': 'ready'})
            logger.info('Added to Redis', extra={'component': 'redis', 'movie_id': mid})


def main_job():
    job_id = str(uuid.uuid4())
    logger.info('Job start', extra={'component': 'scheduler', 'job_id': job_id})
    try:
        data = extract_movies_tv()
        if not data: return
        ids = group_ids(data)
        posters = extract_jpg_paths(ids)
        if posters:
            download_posters(posters)
            push_to_redis(posters)
        logger.info('Job done', extra={'component': 'scheduler', 'job_id': job_id, 'count': len(posters)})
    except Exception as e:
        logger.critical('Job failed', exc_info=True,
                        extra={'component': 'scheduler', 'job_id': job_id, 'error': str(e)})


def health_check():
    try:
        redis_client.ping()
        logger.info('Health OK', extra={'component': 'health'})
        return True
    except Exception as e:
        logger.error('Health failed', exc_info=True, extra={'component': 'health', 'error': str(e)})
        return False


def init():
    global HEADERS, PROXIES, redis_client
    load_dotenv()
    HEADERS = {'accept': 'application/json', 'Authorization': f"Bearer {os.getenv('TMDB_ACCOUNT_BEARER')}"}
    PROXIES = {'http': f"socks5h://{os.getenv('TUNNEL_HOST_NAME')}:{os.getenv('TUNNEL_PORT')}", 
               'https': f"socks5h://{os.getenv('TUNNEL_HOST_NAME')}:{os.getenv('TUNNEL_PORT')}"}
    redis_client = get_redis_client()

if __name__ == '__main__':
    init()
    logger = setup_logging()
    logger.addFilter(RequestContextFilter())

    if not health_check(): logger.warning('Starting degraded')
    main_job()
    schedule.every(40).seconds.do(main_job)
    schedule.every(30).seconds.do(health_check)
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Shutdown')
    except Exception:
        logger.critical('Loop error', exc_info=True)
        raise
