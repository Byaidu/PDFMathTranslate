import unittest
from pdf2zh import cache
from peewee import SqliteDatabase

MODELS = [cache._TranslationCache]
test_db = SqliteDatabase(":memory:")


class TestCache(unittest.TestCase):
    def setUp(self):
        # Bind model classes to test db. Since we have a complete list of
        # all models, we do not need to recursively bind dependencies.
        test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)

        test_db.connect()
        test_db.create_tables(MODELS)

    def tearDown(self):
        # Clean up
        test_db.drop_tables(MODELS)
        test_db.close()

    def test_basic_set_get(self):
        """Test basic set and get operations"""
        cache_instance = cache.TranslationCache("test_engine", "{}")

        # Test get with non-existent entry
        result = cache_instance.get("hello")
        self.assertIsNone(result)

        # Test set and get
        cache_instance.set("hello", "你好")
        result = cache_instance.get("hello")
        self.assertIsNotNone(result)
        self.assertEqual(result.translation, "你好")
        self.assertEqual(result.original_text, "hello")

    def test_cache_overwrite(self):
        """Test that cache entries can be overwritten"""
        cache_instance = cache.TranslationCache("test_engine", "{}")

        # Set initial translation
        cache_instance.set("hello", "你好")

        # Overwrite with new translation
        cache_instance.set("hello", "您好")

        # Verify the new translation is returned
        result = cache_instance.get("hello")
        self.assertEqual(result.translation, "您好")

    def test_engine_distinction(self):
        """Test that cache distinguishes between different translation engines"""
        cache1 = cache.TranslationCache("engine1", "{}")
        cache2 = cache.TranslationCache("engine2", "{}")

        # Set same text with different engines
        cache1.set("hello", "你好 1")
        cache2.set("hello", "你好 2")

        # Verify each engine gets its own translation
        result1 = cache1.get("hello")
        result2 = cache2.get("hello")
        self.assertEqual(result1.translation, "你好 1")
        self.assertEqual(result2.translation, "你好 2")

    def test_params_distinction(self):
        """Test that cache distinguishes between different engine parameters"""
        cache1 = cache.TranslationCache("test_engine", '{"param": "value1"}')
        cache2 = cache.TranslationCache("test_engine", '{"param": "value2"}')

        # Set same text with different parameters
        cache1.set("hello", "你好 1")
        cache2.set("hello", "你好 2")

        # Verify each parameter set gets its own translation
        result1 = cache1.get("hello")
        result2 = cache2.get("hello")
        self.assertEqual(result1.translation, "你好 1")
        self.assertEqual(result2.translation, "你好 2")


if __name__ == "__main__":
    unittest.main()
