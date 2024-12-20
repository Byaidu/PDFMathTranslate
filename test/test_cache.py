import unittest
import os
import tempfile
import shutil
import time
from pdf2zh import cache


class TestCache(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_cache_dir = os.path.join(tempfile.gettempdir(), "test_cache")
        self.original_cache_dir = cache.cache_dir
        cache.cache_dir = self.test_cache_dir
        os.makedirs(self.test_cache_dir, exist_ok=True)

    def tearDown(self):
        # Clean up the test directory
        shutil.rmtree(self.test_cache_dir)
        cache.cache_dir = self.original_cache_dir

    def test_deterministic_hash(self):
        # Test hash generation for different inputs
        test_input = "Hello World"
        hash1 = cache.deterministic_hash(test_input)
        hash2 = cache.deterministic_hash(test_input)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 20)

        # Test different inputs produce different hashes
        hash3 = cache.deterministic_hash("Different input")
        self.assertNotEqual(hash1, hash3)

    def test_get_dirs(self):
        # Create test directories
        test_dirs = ["dir1", "dir2", "dir3"]
        for dir_name in test_dirs:
            os.makedirs(os.path.join(self.test_cache_dir, dir_name))

        # Create a file (should be ignored)
        with open(os.path.join(self.test_cache_dir, "test.txt"), "w") as f:
            f.write("test")

        dirs = cache.get_dirs()
        self.assertEqual(len(dirs), 3)
        for dir_path in dirs:
            self.assertTrue(os.path.isdir(dir_path))

    def test_get_time(self):
        # Create test directory with time file
        test_dir = os.path.join(self.test_cache_dir, "test_dir")
        os.makedirs(test_dir)
        test_time = 1234567890.0

        with open(os.path.join(test_dir, cache.time_filename), "w") as f:
            f.write(str(test_time))

        # Test reading time
        result = cache.get_time(test_dir)
        self.assertEqual(result, test_time)

        # Test non-existent directory
        non_existent_dir = os.path.join(self.test_cache_dir, "non_existent")
        result = cache.get_time(non_existent_dir)
        self.assertEqual(result, float("inf"))

    def test_write_time(self):
        test_dir = os.path.join(self.test_cache_dir, "test_dir")
        os.makedirs(test_dir)

        cache.write_time(test_dir)

        self.assertTrue(os.path.exists(os.path.join(test_dir, cache.time_filename)))
        with open(os.path.join(test_dir, cache.time_filename)) as f:
            time_value = float(f.read())
        self.assertIsInstance(time_value, float)

    def test_remove_extra(self):
        # Create more than max_cache directories
        for i in range(cache.max_cache + 2):
            dir_path = os.path.join(self.test_cache_dir, f"dir{i}")
            os.makedirs(dir_path)
            time.sleep(0.1)  # Ensure different timestamps
            cache.write_time(dir_path)

        cache.remove_extra()

        remaining_dirs = cache.get_dirs()
        self.assertLessEqual(len(remaining_dirs), cache.max_cache)

    def test_cache_operations(self):
        test_hash = "test123hash"
        test_para_hash = "para456hash"
        test_content = "Test paragraph content"

        # Test cache creation
        self.assertFalse(cache.is_cached(test_hash))
        cache.create_cache(test_hash)
        self.assertTrue(cache.is_cached(test_hash))

        # Test paragraph operations
        self.assertIsNone(cache.load_paragraph(test_hash, test_para_hash))
        cache.write_paragraph(test_hash, test_para_hash, test_content)
        self.assertEqual(cache.load_paragraph(test_hash, test_para_hash), test_content)


if __name__ == "__main__":
    unittest.main()
