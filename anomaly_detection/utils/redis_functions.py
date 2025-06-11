import time
from contextlib import contextmanager

import redis
from django.conf import settings

# Setup Redis client
redis_client = redis.StrictRedis.from_url(settings.REDIS_URL)


@contextmanager
def redis_lock(lock_key, timeout=30, wait_interval=1, max_wait=20):
    """
    Context manager to acquire a Redis lock with a timeout and retry mechanism.
    :param lock_key: The key for the Redis lock.
    :param timeout: The duration in seconds for which the lock should be held.
    :param wait_interval: The interval in seconds to wait before retrying to acquire the lock.
    :param max_wait: The maximum time in seconds to wait to acquire the lock before giving up.
    :return: Yields True if the lock was acquired, False otherwise.
    """
    lock_acquired = False
    total_waited = 0

    while not lock_acquired and total_waited < max_wait:
        # Attempt to acquire the lock with NX (set if not exists) and EX (expiration time)
        lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=timeout)
        # If the lock was acquired, break the loop. If not, wait and retry.
        if lock_acquired:
            break
        time.sleep(wait_interval)
        total_waited += wait_interval
        # DELETE: Debug
        if total_waited >= 2:
            print(f"Waiting for lock {lock_key} for {total_waited} seconds...")

    try:
        # Yield the lock status to the context manager caller, indicating if the lock was acquired
        yield lock_acquired
    finally:
        # If the lock was acquired, delete the lock key to release it
        if lock_acquired:
            redis_client.delete(lock_key)
