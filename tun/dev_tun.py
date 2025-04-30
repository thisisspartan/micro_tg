#!/usr/bin/env python3
import requests
import json
import os
import time
import socket
import subprocess
import logging
import sys
import socket
import uuid
import traceback
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = socket.gethostname()
        self.pod_name = os.getenv('POD_NAME', self.hostname)
        self.namespace = os.getenv('POD_NAMESPACE', 'default')
        self.service_name = os.getenv('SERVICE_NAME', 'tunnel-service')
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
    for name in ('requests', 'urllib3', 'ssh'):
        logging.getLogger(name).setLevel(logging.WARNING)
    
    return logger

logger = setup_logging()

# Получение настроек из переменных окружения
SSH_USER = os.environ.get("SSH_USER")
SSH_HOST = os.environ.get("SSH_HOST")
SSH_PORT = os.environ.get("SSH_PORT")
TUNNEL_PORT = int(os.environ.get("TUNNEL_PORT"))  # используем значение по умолчанию, если переменная не задана
SSH_PASS = os.environ.get("SSH_PASS")

# Настройка прокси для requests
PROXIES = {
    'http': f'socks5h://127.0.0.1:{TUNNEL_PORT}',
    'https': f'socks5h://127.0.0.1:{TUNNEL_PORT}'
}

def proxy_checker():
    TARGET_URL = 'https://httpbin.org/ip'
    trace_id = str(uuid.uuid4())
    extra = {
        'component': 'proxy_check',
        'operation': 'health_check',
        'target_url': TARGET_URL,
        'proxy_url': PROXIES['https'],
        'trace_id': trace_id
    }
    
    try:
        logger.info("Starting proxy check", extra=extra)
        response = requests.get(TARGET_URL, proxies=PROXIES, timeout=15)
        response.raise_for_status()
        
        extra.update({'http_status': response.status_code})
        
        try:
            data = response.json()
            ip_address = data.get('origin') or data.get('ip')
            logger.info("Proxy check successful", 
                       extra={**extra, 'proxy_ip': ip_address})
        except json.JSONDecodeError:
            logger.warning("Proxy check unexpected response format",
                          extra={**extra, 'response_body': response.text[:200]})
            
    except requests.exceptions.ProxyError as e:
        logger.error("Proxy connection failed",
                    extra={**extra, 'error': str(e)},
                    exc_info=True)
    except requests.exceptions.ConnectTimeout as e:
        logger.error("--- ОШИБКА: ТАЙМАУТ СОЕДИНЕНИЯ ---")
        logger.error(f"Детали ошибки: {e}")
    except requests.exceptions.SSLError as e:
        logger.error("--- ОШИБКА SSL ---")
        logger.error(f"Детали ошибки: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error("--- ОШИБКА СОЕДИНЕНИЯ ---")
        logger.error(f"Детали ошибки: {e}")
    except requests.exceptions.RequestException as e:
        logger.error("--- ОБЩАЯ ОШИБКА REQUESTS ---")
        logger.error(f"Детали ошибки: {e}")
    except Exception as e:
        logger.error("--- НЕПРЕДВИДЕННАЯ ОШИБКА ---")
        logger.error(f"Детали ошибки: {e}")

def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((host, port))
            return True
        except socket.error:
            return False

def start_ssh_tunnel():
    base_cmd = [
        "sshpass", "-p", f"{SSH_PASS}",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-N", "-D", f"0.0.0.0:{TUNNEL_PORT}",
        "-p", SSH_PORT,
        f"{SSH_USER}@{SSH_HOST}"
    ]
    extra = {
        'component': 'ssh_tunnel',
        'operation': 'start_tunnel',
        'tunnel_port': TUNNEL_PORT,
        'ssh_host': SSH_HOST,
        'ssh_port': SSH_PORT
    }
    
    try:
        subprocess.Popen(base_cmd)
        logger.info("SSH tunnel started", extra=extra)
    except Exception as e:
        logger.error("SSH tunnel startup failed",
                    extra={**extra, 'error': str(e)},
                    exc_info=True)

def main():
    logger.info("Starting SSH tunnel monitoring", 
               extra={'component': 'main', 'operation': 'init'})
    while True:
        extra = {
            'component': 'port_check',
            'port': TUNNEL_PORT,
            'host': '127.0.0.1'
        }
        
        if is_port_in_use("127.0.0.1", TUNNEL_PORT):
            logger.info("Tunnel port is active", extra=extra)
            proxy_checker()
        else:
            logger.warning("Tunnel port not available", extra=extra)
            start_ssh_tunnel()
            proxy_checker()
            
        time.sleep(60)

if __name__ == "__main__":
    main()
