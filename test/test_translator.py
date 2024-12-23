import unittest
from pdf2zh.translator import BaseTranslator
from pdf2zh import cache


class AutoIncreaseTranslator(BaseTranslator):
    name = "auto_increase"
    n = 0

    def do_translate(self, text):
        self.n += 1
        return str(self.n)


class AutoIncreaseAsyncTranslator(BaseTranslator):
    name = "auto_increase_async"
    n = 0

    async def do_translate_async(self, text):
        self.n += 1
        return str(self.n)


class TestTranslator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_db = cache.init_test_db()

    def tearDown(self):
        cache.clean_test_db(self.test_db)

    async def test_cache(self):
        translator = AutoIncreaseTranslator("en", "zh", "test")
        # First translation should be cached
        text = "Hello World"
        first_result = await translator.translate_async(text)

        # Second translation should return the same result from cache
        second_result = await translator.translate_async(text)
        self.assertEqual(first_result, second_result)

        # Different input should give different result
        different_text = "Different Text"
        different_result = await translator.translate_async(different_text)
        self.assertNotEqual(first_result, different_result)

        # Test cache with ignore_cache=True
        translator.ignore_cache = True
        no_cache_result = await translator.translate_async(text)
        self.assertNotEqual(first_result, no_cache_result)

    async def test_add_cache_impact_parameters(self):
        translator = AutoIncreaseTranslator("en", "zh", "test")

        # Test cache with added parameters
        text = "Hello World"
        first_result = await translator.translate_async(text)
        translator.add_cache_impact_parameters("test", "value")
        second_result = await translator.translate_async(text)
        self.assertNotEqual(first_result, second_result)

        # Test cache with ignore_cache=True
        no_cache_result = await translator.translate_async(text, ignore_cache=True)
        self.assertNotEqual(first_result, no_cache_result)

        translator.ignore_cache = True
        no_cache_result = await translator.translate_async(text)
        self.assertNotEqual(first_result, no_cache_result)

        # Test cache with ignore_cache=False
        translator.ignore_cache = False
        cache_result = await translator.translate_async(text)
        self.assertEqual(second_result, cache_result)

        # Test cache with another parameter
        translator.add_cache_impact_parameters("test2", "value2")
        another_result = await translator.translate_async(text)
        self.assertNotEqual(second_result, another_result)

    async def test_base_translator_throw(self):
        translator = BaseTranslator("en", "zh", "test")
        with self.assertRaises(NotImplementedError):
            translator.do_translate("Hello World")
        with self.assertRaises(NotImplementedError):
            await translator.do_translate_async("Hello World")

    async def test_call_sync_from_async(self):
        sync_translator = AutoIncreaseTranslator("en", "zh", "test")

        # call sync from async
        self.assertEqual(await sync_translator.translate_async("Hello World"), "1")


if __name__ == "__main__":
    unittest.main()
