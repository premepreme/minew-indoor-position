import numpy as np
import redis
from core.config import settings

r = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
)

max_lenght = settings.MAX_QUEUE_LENGTH


def enqueue(value: float, key: str):
    r.rpush(key, value)
    if r.llen(key) > max_lenght:
        _ = r.lpop(key)


def get_avg(key: str):
    return np.mean([float(i) for i in r.lrange(key, 0, -1)])
