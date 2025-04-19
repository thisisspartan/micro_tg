#!/usr/bin/env python3
import requests
import json
import os
import time
import socket
import subprocess
import logging
import sys

# Настройка логирования: вывод в stdout, уровень INFO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

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
    logger.info(f"Пытаемся сделать запрос к {TARGET_URL} через прокси: {PROXIES['https']}")
    try:
        response = requests.get(TARGET_URL, proxies=PROXIES, timeout=15)
        response.raise_for_status()
        try:
            data = response.json()
            ip_address = data.get('origin') or data.get('ip')
            logger.info("--- УСПЕХ! ---")
            logger.info(f"Статус код: {response.status_code}")
            logger.info(f"IP-адрес, полученный через прокси: {ip_address}")
        except json.JSONDecodeError:
            logger.info("--- УСПЕХ (ответ не JSON)! ---")
            logger.info(f"Статус код: {response.status_code}")
            logger.info(f"Содержимое ответа: {response.text}")
    except requests.exceptions.ProxyError as e:
        logger.error("--- ОШИБКА ПРОКСИ ---")
        logger.error(f"Не удалось подключиться к прокси: {PROXIES['https']}")
        logger.error(f"Детали ошибки: {e}")
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
    try:
        subprocess.Popen(base_cmd)
        logger.info(f"SSH туннель запущен на порту {TUNNEL_PORT} "
                    f"(соединение с {SSH_USER}@{SSH_HOST}:{SSH_PORT})")
    except Exception as ex:
        logger.error(f"Не удалось запустить SSH туннель: {ex}")

def main():
    logger.info("Запуск мониторинга SSH туннеля...")
    while True:
        if is_port_in_use("127.0.0.1", TUNNEL_PORT):
            logger.info(f"Порт {TUNNEL_PORT} занят; туннель активен.")
            proxy_checker()
        else:
            logger.info(f"Порт {TUNNEL_PORT} свободен; пробуем запустить SSH туннель...")
            start_ssh_tunnel()
            proxy_checker()
        time.sleep(60)

if __name__ == "__main__":
    main()
