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

    def test_non_string_params(self):
        """Test that non-string parameters are automatically converted to JSON"""
        params = {"model": "gpt-3.5", "temperature": 0.7}
        cache_instance = cache.TranslationCache("test_engine", params)

        # Test that params are converted to JSON string
        self.assertEqual(
            cache_instance.translate_engine_params,
            '{"model": "gpt-3.5", "temperature": 0.7}',
        )

        # Test that cache operations work with converted params
        cache_instance.set("hello", "你好")
        result = cache_instance.get("hello")
        self.assertEqual(result.translation, "你好")

        # Test with different param types
        array_params = ["param1", "param2"]
        cache_instance2 = cache.TranslationCache("test_engine", array_params)
        self.assertEqual(cache_instance2.translate_engine_params, '["param1", "param2"]')

        # Test with nested structures
        nested_params = {"options": {"temp": 0.8, "models": ["a", "b"]}}
        cache_instance3 = cache.TranslationCache("test_engine", nested_params)
        self.assertEqual(
            cache_instance3.translate_engine_params,
            '{"options": {"models": ["a", "b"], "temp": 0.8}}',
        )

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

    def test_consistent_param_serialization(self):
        """Test that dictionary parameters are consistently serialized regardless of key order"""
        # Test simple dictionary
        params1 = {"b": 1, "a": 2}
        params2 = {"a": 2, "b": 1}
        cache1 = cache.TranslationCache("test_engine", params1)
        cache2 = cache.TranslationCache("test_engine", params2)
        self.assertEqual(cache1.translate_engine_params, cache2.translate_engine_params)

        # Test nested dictionary
        params1 = {"outer2": {"inner2": 2, "inner1": 1}, "outer1": 3}
        params2 = {"outer1": 3, "outer2": {"inner1": 1, "inner2": 2}}
        cache1 = cache.TranslationCache("test_engine", params1)
        cache2 = cache.TranslationCache("test_engine", params2)
        self.assertEqual(cache1.translate_engine_params, cache2.translate_engine_params)

        # Test dictionary with list of dictionaries
        params1 = {"b": [{"y": 1, "x": 2}], "a": 3}
        params2 = {"a": 3, "b": [{"x": 2, "y": 1}]}
        cache1 = cache.TranslationCache("test_engine", params1)
        cache2 = cache.TranslationCache("test_engine", params2)
        self.assertEqual(cache1.translate_engine_params, cache2.translate_engine_params)

        # Test that different values still produce different results
        params1 = {"a": 1, "b": 2}
        params2 = {"a": 2, "b": 1}
        cache1 = cache.TranslationCache("test_engine", params1)
        cache2 = cache.TranslationCache("test_engine", params2)
        self.assertNotEqual(cache1.translate_engine_params, cache2.translate_engine_params)

    def test_cache_with_sorted_params(self):
        """Test that cache works correctly with sorted parameters"""
        params1 = {"b": [{"y": 1, "x": 2}], "a": 3}
        params2 = {"a": 3, "b": [{"x": 2, "y": 1}]}

        # Both caches should work with the same key
        cache1 = cache.TranslationCache("test_engine", params1)
        cache1.set("hello", "你好")

        cache2 = cache.TranslationCache("test_engine", params2)
        result = cache2.get("hello")

        self.assertIsNotNone(result)
        self.assertEqual(result.translation, "你好")


if __name__ == "__main__":
    unittest.main()
