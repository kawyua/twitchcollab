import os

import redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv

load_dotenv()

listen = ['high', 'default', 'low']

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
ENV = os.getenv("ENV")

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        #if windows machine
        if ENV == 'dev':
            from rq_win import WindowsWorker
            worker = WindowsWorker(map(Queue, listen))
        else:
            worker = Worker(map(Queue, listen))
        worker.work()
