import unittest
from pdf2zh.translator import BaseTranslator
from pdf2zh import cache
from pdf2zh.translator import RateLimiter
import threading
import time


class AutoIncreaseTranslator(BaseTranslator):
    name = "auto_increase"
    n = 0

    def do_translate(self, text):
        self.n += 1
        return str(self.n)


class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.test_db = cache.init_test_db()

    def tearDown(self):
        cache.clean_test_db(self.test_db)

    def test_cache(self):
        translator = AutoIncreaseTranslator("en", "zh", "test")
        # First translation should be cached
        text = "Hello World"
        first_result = translator.translate(text)

        # Second translation should return the same result from cache
        second_result = translator.translate(text)
        self.assertEqual(first_result, second_result)

        # Different input should give different result
        different_text = "Different Text"
        different_result = translator.translate(different_text)
        self.assertNotEqual(first_result, different_result)

        # Test cache with ignore_cache=True
        translator.ignore_cache = True
        no_cache_result = translator.translate(text)
        self.assertNotEqual(first_result, no_cache_result)

    def test_add_cache_impact_parameters(self):
        translator = AutoIncreaseTranslator("en", "zh", "test")

        # Test cache with added parameters
        text = "Hello World"
        first_result = translator.translate(text)
        translator.add_cache_impact_parameters("test", "value")
        second_result = translator.translate(text)
        self.assertNotEqual(first_result, second_result)

        # Test cache with ignore_cache=True
        no_cache_result = translator.translate(text, ignore_cache=True)
        self.assertNotEqual(first_result, no_cache_result)

        translator.ignore_cache = True
        no_cache_result = translator.translate(text)
        self.assertNotEqual(first_result, no_cache_result)

        # Test cache with ignore_cache=False
        translator.ignore_cache = False
        cache_result = translator.translate(text)
        self.assertEqual(second_result, cache_result)

        # Test cache with another parameter
        translator.add_cache_impact_parameters("test2", "value2")
        another_result = translator.translate(text)
        self.assertNotEqual(second_result, another_result)

    def test_base_translator_throw(self):
        translator = BaseTranslator("en", "zh", "test")
        with self.assertRaises(NotImplementedError):
            translator.translate("Hello World")


class TestRateLimiter(unittest.TestCase):
    def test_concurrent_rate_limit(self):
        limiter = RateLimiter(10)  # 10 QPS
        start_time = time.time()
        timestamps = [None for _ in range(20)]

        def task(i):
            limiter.wait()
            timestamps[i] = time.time()

        # Run 20 concurrent tasks
        tasks = [threading.Thread(target=task, args=(i,)) for i in range(20)]

        # Start the tasks
        for task in tasks:
            task.start()

        # Wait for all tasks to complete
        for task in tasks:
            task.join()

        # Verify timing
        total_time = timestamps[-1] - start_time
        self.assertGreaterEqual(
            total_time, 1.0
        )  # Should take at least 1s for 20 requests at 10 QPS

        # Check even distribution
        intervals = [
            timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)
        ]
        avg_interval = sum(intervals) / len(intervals)
        self.assertAlmostEqual(
            avg_interval, 0.1, delta=0.05
        )  # Should be close to 0.1s (1/10 QPS)

    def test_burst_handling(self):
        limiter = RateLimiter(10)  # 10 QPS

        # First burst of 5 requests should be immediate
        start = time.time()
        tasks = [threading.Thread(target=limiter.wait) for _ in range(5)]
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()
        burst_time = time.time() - start

        self.assertLess(burst_time, 0.1)  # Should complete quickly


if __name__ == "__main__":
    unittest.main()
