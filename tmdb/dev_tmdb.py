# docker run --rm -it --network host --name my_dev_tmdb --env-file .env dev_tmdb 
# docker run --rm -it --name my_dev_tmdb --env-file .env dev_tmdb 
import os
import time
import json
import logging
import requests
import redis
import schedule
from dotenv import load_dotenv

# Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env файла
load_dotenv()
TMDB_ACCOUNT_ID = os.environ.get('TMDB_ACCOUNT_ID')
TMDB_ACCOUNT_BEARER = os.environ.get('TMDB_ACCOUNT_BEARER')
TUNNEL_PORT = int(os.environ.get("TUNNEL_PORT"))
TUNNEL_HOST_NAME = os.environ.get("TUNNEL_HOST_NAME")
# print(TMDB_ACCOUNT_ID)

# Подключение к Redis
# redis_client = redis.Redis(host='localhost', port=6379, db=0)


try:
    redis_client = redis.Redis(host=os.environ.get('REDIS_HOST'),
                    port=int(os.environ.get('REDIS_PORT')),
                    db=int(os.environ.get('REDIS_DB', 0)))
    logging.info("Connected to Redis")
except Exception as e:
    logging.error("Failed to connect to Redis: %s", str(e))
    raise
# Конфигурация прокси
PROXIES = {
    'http': f'socks5h://{TUNNEL_HOST_NAME}:{TUNNEL_PORT}',
    'https': f'socks5h://{TUNNEL_HOST_NAME}:{TUNNEL_PORT}'
}

# PROXIES = {
#     'http': f'socks5h://127.0.0.1:{TUNNEL_PORT}',
#     'https': f'socks5h://127.0.0.1:{TUNNEL_PORT}'
# }

# Словарь URL для запросов к TMDB
URLS = {
    "movies": f"https://api.themoviedb.org/3/account/{TMDB_ACCOUNT_ID}/favorite/movies?language=en-US&page=1&sort_by=created_at.asc",
    "tv": f"https://api.themoviedb.org/3/account/{TMDB_ACCOUNT_ID}/favorite/tv?language=en-US&page=1&sort_by=created_at.asc",
}

# Заголовки для запросов к TMDB
HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCOUNT_BEARER}"
}


def find_keys_grouped(data, primary_key, other_keys, result=None):
    """
    Рекурсивно ищет в данных значение primary_key и группирует значения other_keys.
    
    :param data: JSON данные (dict или list)
    :param primary_key: ключ, по которому группируем данные
    :param other_keys: список других ключей, значения которых нужно собирать в список
    :param result: аккумулятор для результатов (используется рекурсивно)
    :return: словарь сгруппированных значений
    """
    if result is None:
        result = {}
    if isinstance(data, dict):
        primary_value = data.get(primary_key)
        if primary_value is not None:
            if primary_value not in result:
                result[primary_value] = {key: [] for key in other_keys}
            for key in other_keys:
                if key in data:
                    result[primary_value][key].append(data[key])
        for value in data.values():
            find_keys_grouped(value, primary_key, other_keys, result)
    elif isinstance(data, list):
        for item in data:
            find_keys_grouped(item, primary_key, other_keys, result)
    return result


def extract_movies_tv():
    """
    Делает запросы к TMDB API для получения данных о любимых фильмах и сериалах.
    
    :return: список полученных JSON объектов
    """
    data_list = []
    for key, url in URLS.items():
        try:
            response = requests.get(url, headers=HEADERS, proxies=PROXIES)
            response.raise_for_status()
            data = response.json()
            data_list.append(data)
            logger.info("Успешно получены данные для %s", key)
        except requests.RequestException as e:
            logger.error("Ошибка при получении данных для %s: %s", key, e)
    return data_list


def extract_jpgs_path(id_dict):
    """
    Получает пути к изображению (постеру) для каждого фильма/сериала.
    
    :param id_dict: словарь с идентификаторами и дополнительными данными (например, vote_average)
    :return: словарь, где ключ – id, а значение – список, содержащий путь к изображению и дополнительные данные
    """
    posters = {}
    url_template_movie = "https://api.themoviedb.org/3/movie/{}/images?language=ru"
    url_template_tv = "https://api.themoviedb.org/3/tv/{}/images?language=ru"
    
    for movie_id in id_dict:
        endpoints = {
            'movie': url_template_movie.format(movie_id),
            'tv': url_template_tv.format(movie_id)
        }
        for category, endpoint in endpoints.items():
            try:
                response = requests.get(endpoint, headers=HEADERS, proxies=PROXIES)
                response.raise_for_status()
                json_data = response.json()
                # Если ключ success отсутствует и есть постеры
                if not json_data.get('success') and json_data.get('posters'):
                    poster_path = json_data['posters'][0].get('file_path')
                    if poster_path:
                        # Сохраняем и выходим из цикла для данного id
                        posters[movie_id] = [poster_path] + [id_dict[movie_id]]
                        logger.info("Получен путь постера для id: %s", movie_id)
                        break
            except requests.RequestException as e:
                logger.error("Ошибка при получении изображений для id %s: %s", movie_id, e)
    return posters


def download_posters(posters):
    """
    Загружает постеры по заданным путям и сохраняет их локально.
    
    :param posters: словарь с id и данными о постерах
    """
    base_url = "https://image.tmdb.org/t/p/w500{}"
    os.makedirs("jpgs", exist_ok=True)
    for movie_id, data in posters.items():
        poster_path = data[0]
        full_url = base_url.format(poster_path)
        try:
            response = requests.get(full_url, proxies=PROXIES)
            response.raise_for_status()
            filename = poster_path.replace('/', '')
            file_path = os.path.join("jpgs", filename)
            with open(file_path, "wb") as file:
                file.write(response.content)
            logger.info("Постер для id %s сохранен в %s", movie_id, file_path)
        except requests.RequestException as e:
            logger.error("Ошибка при скачивании постера для id %s: %s", movie_id, e)


def posters_dict_to_redis(posters):
    """
    Преобразует словарь с данными постеров в формат, подходящий для хранения в Redis.
    
    :param posters: словарь с данными постеров
    :return: JSON-строка преобразованных данных
    """
    transformed_dict = {}
    for movie_id, data in posters.items():
        image_name = data[0].lstrip('/')
        vote_average = str(data[1]['vote_average'][0]) if data[1].get('vote_average') else "0"
        transformed_dict[str(movie_id)] = {
            'jpg': image_name,
            'vote_average': vote_average
        }
    logger.info("Преобразованный словарь для Redis: %s", transformed_dict)
    return json.dumps(transformed_dict)


def put_to_redis(posters_data_json):
    """
    Сохраняет данные постеров в Redis (если запись с данным id ещё отсутствует).
    
    :param posters_data_json: JSON-строка с данными постеров
    """
    posters_data = json.loads(posters_data_json)
    for movie_id, data in posters_data.items():
        redis_key = f"poster:{movie_id}"
        if not redis_client.exists(redis_key):
            # hmset устарел, но для простоты оставляем; можно заменить на hset с mapping
            redis_client.hmset(redis_key, {
                "jpg": data["jpg"],
                "vote_average": data["vote_average"],
                "status": "ready"
            })
            logger.info("Добавлен постер для id %s в Redis", movie_id)
        else:
            logger.info("Постер для id %s уже присутствует в Redis", movie_id)


def main_job():
    """
    Основная функция, объединяющая весь процесс:
    1. Получение данных о фильмах и сериалах
    2. Извлечение необходимых полей
    3. Получение пути к постерам
    4. Скачивание изображений
    5. Сохранение метаданных в Redis
    """
    logger.info("Запуск основного задания")
    unsorted_data = extract_movies_tv()
    if not unsorted_data:
        logger.error("Данные не получены, прерывание задания")
        return

    id_dict = find_keys_grouped(unsorted_data, "id", ["vote_average"])
    if not id_dict:
        logger.error("Не удалось сформировать словарь id, прерывание задания")
        return

    posters = extract_jpgs_path(id_dict)
    if not posters:
        logger.warning("Постеры не найдены")
        return

    posters_data_json = posters_dict_to_redis(posters)
    download_posters(posters)
    put_to_redis(posters_data_json)
    logger.info("Основное задание успешно выполнено")


if __name__ == "__main__":
    # Запускаем основное задание сразу при старте
    main_job()
    
    # Планируем запуск основного задания каждые 40 секунд
    schedule.every(40).seconds.do(main_job)
    while True:
        schedule.run_pending()
        time.sleep(1)
