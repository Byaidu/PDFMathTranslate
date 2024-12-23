import os
import json
from peewee import Model, SqliteDatabase, AutoField, CharField, TextField, SQL

# we don't init the database here
db = SqliteDatabase(None)


class _TranslationCache(Model):
    id = AutoField()
    translate_engine = CharField(max_length=20)
    translate_engine_params = TextField()
    original_text = TextField()
    translation = TextField()

    class Meta:
        database = db
        constraints = [
            SQL(
                """
            UNIQUE (
                translate_engine,
                translate_engine_params,
                original_text
                )
            ON CONFLICT REPLACE
            """
            )
        ]


class TranslationCache:
    @staticmethod
    def _sort_dict_recursively(obj):
        if isinstance(obj, dict):
            return {k: TranslationCache._sort_dict_recursively(v) for k in sorted(obj.keys()) for v in [obj[k]]}
        elif isinstance(obj, list):
            return [TranslationCache._sort_dict_recursively(item) for item in obj]
        return obj

    def __init__(self, translate_engine, translate_engine_params):
        self.translate_engine = translate_engine
        self.update_params(translate_engine_params)

    def update_params(self, params):
        if not isinstance(params, str):
            params = self._sort_dict_recursively(params)
            params = json.dumps(params)
        self.translate_engine_params = params

    def get(self, original_text):
        return _TranslationCache.get_or_none(
            translate_engine=self.translate_engine,
            translate_engine_params=self.translate_engine_params,
            original_text=original_text,
        )

    def set(self, original_text, translation):
        _TranslationCache.create(
            translate_engine=self.translate_engine,
            translate_engine_params=self.translate_engine_params,
            original_text=original_text,
            translation=translation,
        )


def init_db(remove_exists=False):
    cache_folder = os.path.join(os.path.expanduser("~"), ".cache", "pdf2zh")
    os.makedirs(cache_folder, exist_ok=True)
    # The current version does not support database migration, so add the version number to the file name.
    cache_db_path = os.path.join(cache_folder, "cache.v1.db")
    if remove_exists and os.path.exists(cache_db_path):
        os.remove(cache_db_path)
    db.init(
        cache_db_path,
        pragmas={
            "journal_mode": "wal",
            "busy_timeout": 1000,
        },
    )
    db.create_tables([_TranslationCache], safe=True)


init_db()
