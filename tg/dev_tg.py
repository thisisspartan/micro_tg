import os
import redis
import requests
import logging
import time
import json
from dotenv import load_dotenv
import schedule
# Load environment variables from .env file
load_dotenv()

# Configure logging to output to STDOUT
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Connect to Redis
try:
    r = redis.Redis(host=os.environ.get('REDIS_HOST'),
                    port=int(os.environ.get('REDIS_PORT')),
                    db=int(os.environ.get('REDIS_DB', 0)))
    logging.info("Connected to Redis")
except Exception as e:
    logging.error("Failed to connect to Redis: %s", str(e))
    raise

# Get required variables from environment
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')
TG_FILM_BOT_TOKEN = os.environ.get('TG_FILM_BOT_TOKEN')

if not TG_CHAT_ID or not TG_FILM_BOT_TOKEN:
    logging.error("Environment variables TG_CHAT_ID or TG_FILM_BOT_TOKEN are not set")
    exit(1)

def publish_poster(movie_id, jpg, vote_average):
    """
    Publish the poster image to the Telegram chat via bot API.
    """
    url = f"https://api.telegram.org/bot{TG_FILM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TG_CHAT_ID,
        "caption": f"TMDB: {vote_average}",
        "parse_mode": "HTML"
    }
    
    try:
        os.makedirs("jpgs", exist_ok=True)
        with open(f"jpgs/{jpg}", "rb") as photo:
            response = requests.post(url, data=payload, files={"photo": photo})
        if response.status_code == 200:
            logging.info("✅ Successfully sent %s for movie %s", jpg, movie_id)
            return True
        else:
            logging.error("Failed to send %s for movie %s: %s", jpg, movie_id, response.text)
            return False
    except Exception as e:
        logging.exception("Exception while sending %s for movie %s: %s", jpg, movie_id, str(e))
        return False


def process_posters():
    """
    Process the queue of posters ready for publishing.
    """
    try:
        all_poster_keys = r.keys(b"poster:*")
        logging.info("Found %d poster key(s) in Redis", len(all_poster_keys))
    except Exception as e:
        logging.error("Error retrieving keys from Redis: %s", str(e))
        return

    for key in all_poster_keys:
        key_str = key.decode('utf-8')
        movie_id = key_str.split(':')[1]

        # Get poster data
        poster_data = r.hgetall(key)

        # Check publication status
        status = poster_data.get(b'status', b'').decode('utf-8')
        if status == "published":
            logging.info("Skipping already published poster for movie %s", movie_id)
            continue

        jpg = poster_data.get(b'jpg', b'').decode('utf-8')
        vote_average = poster_data.get(b'vote_average', b'').decode('utf-8')

        # Publish the poster
        if publish_poster(movie_id, jpg, vote_average):
            r.hset(key, "status", "published")
            logging.info("Successfully published poster for movie %s", movie_id)
        else:
            logging.warning("Failed to publish poster for movie %s, will retry later", movie_id)


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
