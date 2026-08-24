import time


class RateLimiter:
    def __init__(self, rate: float, capacity: int):
        """
        :param rate:     Tokens added per second.
        :param capacity: Maximum tokens the bucket can hold.
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def allow_request(self) -> bool:
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


def main():
    limiter = RateLimiter(rate=5, capacity=5)  # 5 tokens/sec, burst of 5

    print("Sending 10 rapid requests (rate=5/s, capacity=5):")
    for i in range(10):
        allowed = limiter.allow_request()
        status = "ALLOWED" if allowed else "DENIED"
        print(f"  Request {i + 1}: {status}")
        time.sleep(0.1)  # 100ms between requests -> only 0.5 tokens refilled each


if __name__ == "__main__":
    main()
