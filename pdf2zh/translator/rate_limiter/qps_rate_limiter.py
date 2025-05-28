import threading
import time

from pdf2zh.translator.base_rate_limiter import BaseRateLimiter


class QPSRateLimiter(BaseRateLimiter):
    def __init__(self, max_qps: int):
        self.max_qps = max_qps
        self.min_interval = 1.0 / max_qps
        self.last_requests = []  # Track last N requests
        self.window_size = max_qps  # Track requests in a sliding window
        self.lock = threading.Lock()

    def wait(self, _rate_limit_params: dict = None):
        with self.lock:
            now = time.time()

            # Clean up old requests outside the 1-second window
            while self.last_requests and now - self.last_requests[0] > 1.0:
                self.last_requests.pop(0)

            # If we have less than max_qps requests in the last second, allow immediately
            if len(self.last_requests) < self.max_qps:
                self.last_requests.append(now)
                return

            # Otherwise, wait until we can make the next request
            next_time = self.last_requests[0] + 1.0
            if next_time > now:
                time.sleep(next_time - now)
            self.last_requests.pop(0)
            self.last_requests.append(next_time)

    def set_max_qps(self, max_qps):
        self.max_qps = max_qps
        self.min_interval = 1.0 / max_qps
        self.window_size = max_qps
