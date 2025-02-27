import toml
from pathlib import Path
from threading import RLock  # 改成 RLock
import os
import copy
import re
from typing import List
import logging

log = logging.getLogger(__name__)


class ConfigManager:
    _instance = None
    _lock = RLock()  # 用 RLock 替换 Lock，允许在同一个线程中重复获取锁

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self, config_path=None, versioncheck=False, version="0.0.0"):
        # 防止重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        if config_path:
            self._config_path = Path(config_path).resolve()
        else:
            self._config_path = (
                Path.home() / ".config" / "PDFMathTranslate" / "config.toml"
            )

        self._config_data = {"global": {}, "translators": {}}
        self.load_env_variables()
        self.load_default_values()
        if versioncheck:
            self._save_config(
                Path.home() / ".config" / "PDFMathTranslate" / f"config.{version}.toml"
            )
        else:
            self._ensure_config_exists()

    def _ensure_config_exists(self, isInit=True):
        """确保配置文件存在，如果不存在则创建默认配置"""
        # 这里也不需要显式再次加锁，原因同上，方法体中再调用 _load_config()，
        # 而 _load_config() 内部会加锁。因为 RLock 是可重入的，不会阻塞。
        if not self._config_path.exists():
            if isInit:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                self._save_config(self._config_path)
            else:
                raise ValueError(f"config file {self._config_path} not found!")
        else:
            self._load_config()

    def _load_config(self):
        with self._lock:
            with self._config_path.open("r", encoding="utf-8") as f:
                loaded_data = toml.load(f)
                self._config_data = {
                    "global": loaded_data.get("global", {}),
                    "translators": {},
                }
                for name, envs in loaded_data.get("translators", {}).items():
                    self._config_data["translators"][name] = envs

    def _save_config(self, config_path):
        with self._lock:
            cleaned_data = self._remove_circular_references(self._config_data)
            if not isinstance(cleaned_data, dict):
                raise ValueError("Invalid data type for config file")
            with config_path.open("w", encoding="utf-8") as f:
                toml.dump(cleaned_data, f)

    def _remove_circular_references(self, obj, seen=None):
        if seen is None:
            seen = set()
        obj_id = id(obj)
        if obj_id in seen:
            return {}
        seen.add(obj_id)

        if isinstance(obj, dict):
            return {
                str(k): (
                    self._remove_circular_references(v, seen)
                    if isinstance(v, (dict, list))
                    else v
                )
                for k, v in obj.items()
                if isinstance(k, str) and not isinstance(v, (float, int, bool))
            }
        elif isinstance(obj, list):
            return [
                (
                    self._remove_circular_references(i, seen)
                    if isinstance(i, (dict, list))
                    else i
                )
                for i in obj
            ]
        elif isinstance(obj, str):
            return obj
        return str(obj)

    def load_default_values(self):
        default_keys = {
            "PDF2ZH_LANG_FROM": "English",
            "PDF2ZH_LANG_TO": "Simplified Chinese",
            "CELERY_BROKER": "redis://127.0.0.1:6379/0",
            "CELERY_RESULT": "redis://127.0.0.1:6379/0",
            "USE_MODELSCOPE": "0",
        }
        for key, value in default_keys.items():
            self._config_data["global"][key] = value

        translator_classes = []
        try:
            from pdf2zh.translator import (
                GoogleTranslator,
                BingTranslator,
                DeepLTranslator,
                DeepLXTranslator,
                OllamaTranslator,
                XinferenceTranslator,
                AzureOpenAITranslator,
                OpenAITranslator,
                ZhipuTranslator,
                ModelScopeTranslator,
                SiliconTranslator,
                GeminiTranslator,
                AzureTranslator,
                TencentTranslator,
                DifyTranslator,
                AnythingLLMTranslator,
                ArgosTranslator,
                GorkTranslator,
                GroqTranslator,
                DeepseekTranslator,
                OpenAIlikedTranslator,
                QwenMtTranslator,
            )

            translator_classes.extend(
                [
                    GoogleTranslator,
                    BingTranslator,
                    DeepLTranslator,
                    DeepLXTranslator,
                    OllamaTranslator,
                    XinferenceTranslator,
                    AzureOpenAITranslator,
                    OpenAITranslator,
                    ZhipuTranslator,
                    ModelScopeTranslator,
                    SiliconTranslator,
                    GeminiTranslator,
                    AzureTranslator,
                    TencentTranslator,
                    DifyTranslator,
                    AnythingLLMTranslator,
                    ArgosTranslator,
                    GorkTranslator,
                    GroqTranslator,
                    DeepseekTranslator,
                    OpenAIlikedTranslator,
                    QwenMtTranslator,
                ]
            )
        except ImportError as e:
            log.error(f"Warning: Failed to import some translator classes: {e}")

        for translator_class in translator_classes:
            name = translator_class.name
            envs = translator_class.envs
            self._config_data["translators"][name] = envs

    def load_env_variables(self):
        for key, value in os.environ.items():
            if key.startswith("PDF2ZH_"):
                if key not in self._config_data["global"]:
                    self._config_data["global"][key] = value

    @classmethod
    def custom_config(cls, file_path):
        """使用自定义路径加载配置文件"""
        custom_path = Path(file_path).resolve()
        if not custom_path.exists():
            raise ValueError(f"Config file {custom_path} not found!")

        with cls._lock:
            cls._instance = cls(config_path=custom_path)

    @classmethod
    def get(cls, key, default=None):
        """获取配置值"""
        instance = cls.get_instance()
        # 读取时，加锁或不加锁都行。但为了统一，我们在修改配置前后都要加锁。
        # get 只要最终需要保存，则会加锁 -> _save_config()
        if key in instance._config_data:
            return instance._config_data[key]

        # 若环境变量中存在该 key，则使用环境变量并写回 config
        if key in os.environ:
            value = os.environ[key]
            instance._config_data[key] = value
            instance._save_config(instance._config_path)
            return value

        # 若 default 不为 None，则设置并保存
        if default is not None:
            instance._config_data[key] = default
            instance._save_config(instance._config_path)
            return default
        return default

    @classmethod
    def set(cls, key, value):
        """设置配置值并保存"""
        instance = cls.get_instance()
        with instance._lock:
            instance._config_data[key] = value
            instance._save_config(instance._config_path)

    @classmethod
    def get_translator_by_name(cls, name):
        """根据 name 获取对应的 translator 配置"""
        instance = cls.get_instance()
        translators = instance._config_data["translators"].get(name, {})
        if translators == {}:
            raise ValueError("no translator config found.")
        return translators

    @classmethod
    def set_translator_by_name(cls, name: str, envs: dict):
        """根据 name 设置或更新 translator 配置"""
        instance = cls.get_instance()
        with instance._lock:
            instance._config_data["translators"][name] = copy.deepcopy(envs)
            instance._save_config(instance._config_path)

    @classmethod
    def get_env_by_translatername(cls, translater_name, name, default=None):
        """根据 name 获取对应的 translator 的具体配置"""
        instance = cls.get_instance()
        type(translater_name)
        translator = instance._config_data["translators"].get(translater_name.name, {})
        if translator:
            if name in translator.keys():
                return translator[name]
            else:
                with instance._lock:
                    instance._config_data["translators"][translater_name.name][
                        name
                    ] = default
                    instance._save_config(instance._config_path)
                    return default
        else:
            with instance._lock:
                instance._config_data["translators"][translater_name.name][
                    name
                ] = default
                instance._save_config(instance._config_path)
                return default

    @classmethod
    def delete(cls, key):
        """删除配置值并保存"""
        instance = cls.get_instance()
        with instance._lock:
            if key in instance._config_data:
                del instance._config_data[key]
                instance._save_config(instance._config_path)

    @classmethod
    def clear(cls):
        """删除配置值并保存"""
        instance = cls.get_instance()
        with instance._lock:
            instance._config_data = {}
            instance._save_config(instance._config_path)

    @classmethod
    def all(cls):
        """返回所有配置项"""
        instance = cls.get_instance()
        # 这里只做读取操作，一般可不加锁。不过为了保险也可以加锁。
        return instance._config_data, instance._config_path

    @classmethod
    def gap(cls):
        """
        Convert a JSON file to a TOML file.
        :param json_file: Path to the input JSON file.
        :param toml_file: Path to the output TOML file.
        """
        newtoml = Path.home() / ".config" / "PDFMathTranslate" / "config.toml"
        json_file = Path.home() / ".config" / "PDFMathTranslate" / "config.json"
        backupfile = Path.home() / ".config" / "PDFMathTranslate" / "config.backup.json"
        if os.path.exists(json_file):
            import json

            newdata = cls.get_instance()._config_data
            try:
                with open(json_file, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                for key, value in data.items():
                    if key != "translators":
                        newdata["global"][key] = value
                for t in data["translators"]:
                    newdata["translators"][t["name"]] = t["envs"]
                with open(newtoml, "w", encoding="utf-8") as tf:
                    toml.dump(newdata, tf)

                # os.remove(json_file)
            except Exception as e:
                log.error(f"Error during conversion: {e}")
        if os.path.exists(backupfile):
            os.remove(backupfile)

    @classmethod
    def versionconfigcheck(cls, version: str):
        newfilename = (
            Path.home()
            / ".config"
            / "PDFMathTranslate"
            / f'config.{".".join(version.split(".")[:3])}.toml'
        )
        if get_versioned_config_files(Path.home() / ".config" / "PDFMathTranslate"):
            log.info("config exist")
            if (
                compare_versions(
                    version,
                    get_versioned_config_files(
                        Path.home() / ".config" / "PDFMathTranslate"
                    )[0][1],
                )
                > -1
            ):
                delete_and_create_file(
                    get_versioned_config_files(
                        Path.home() / ".config" / "PDFMathTranslate"
                    )[0][0],
                    newfilename,
                )
        else:
            cls(versioncheck=True, version=version)


class DefaultConfig:
    def __init__(self):
        self._config_data = {"global": {}, "translators": {}}

    def load_default_values(self):
        default_keys = {
            "PDF2ZH_LANG_FROM": "English",
            "PDF2ZH_LANG_TO": "Simplified Chinese",
            "CELERY_BROKER": "redis://127.0.0.1:6379/0",
            "CELERY_RESULT": "redis://127.0.0.1:6379/0",
            "USE_MODELSCOPE": "0",
        }
        for key, value in default_keys.items():
            self._config_data["global"][key] = value

        translator_classes = []
        try:
            from pdf2zh.translator import (
                GoogleTranslator,
                BingTranslator,
                DeepLTranslator,
                DeepLXTranslator,
                OllamaTranslator,
                XinferenceTranslator,
                AzureOpenAITranslator,
                OpenAITranslator,
                ZhipuTranslator,
                ModelScopeTranslator,
                SiliconTranslator,
                GeminiTranslator,
                AzureTranslator,
                TencentTranslator,
                DifyTranslator,
                AnythingLLMTranslator,
                ArgosTranslator,
                GorkTranslator,
                GroqTranslator,
                DeepseekTranslator,
                OpenAIlikedTranslator,
                QwenMtTranslator,
            )

            translator_classes.extend(
                [
                    GoogleTranslator,
                    BingTranslator,
                    DeepLTranslator,
                    DeepLXTranslator,
                    OllamaTranslator,
                    XinferenceTranslator,
                    AzureOpenAITranslator,
                    OpenAITranslator,
                    ZhipuTranslator,
                    ModelScopeTranslator,
                    SiliconTranslator,
                    GeminiTranslator,
                    AzureTranslator,
                    TencentTranslator,
                    DifyTranslator,
                    AnythingLLMTranslator,
                    ArgosTranslator,
                    GorkTranslator,
                    GroqTranslator,
                    DeepseekTranslator,
                    OpenAIlikedTranslator,
                    QwenMtTranslator,
                ]
            )
        except ImportError as e:
            log.error(f"Warning: Failed to import some translator classes: {e}")

        for translator_class in translator_classes:
            name = translator_class.name
            envs = translator_class.envs
            self._config_data["translators"][name] = envs

    def load_env_variables(self):
        for key, value in os.environ.items():
            if key.startswith("PDF2ZH_"):
                if key not in self._config_data["global"]:
                    self._config_data["global"][key] = value

    def save_config(self, config_path):
        with Path(config_path).open("w", encoding="utf-8") as f:
            toml.dump(self._config_data, f)

    def default_config(self):
        return self._config_data

    def load_config(self, config_path):
        if Path(config_path).exists():
            with Path(config_path).open("r", encoding="utf-8") as f:
                loaded_data = toml.load(f)
                self._config_data = {
                    "global": loaded_data.get("global", {}),
                    "translators": {},
                }
                for name, envs in loaded_data.get("translators", {}).items():
                    self._config_data["translators"][name] = envs


def get_versioned_config_files(directory):
    """
    获取指定目录下所有以 'config' 开头且包含版本号（格式: X.Y.Z）的文件名，并返回版本号。
    :param directory: 目标目录路径
    :return: 版本号列表
    """
    version_pattern = re.compile(r"(\d+\.\d+\.\d+)")
    try:
        files = [
            f
            for f in os.listdir(directory)
            if f.startswith("config") and os.path.isfile(os.path.join(directory, f))
        ]
        return [
            (os.path.join(directory, f), match.groups()[-1])
            for f in files
            if (match := version_pattern.search(f))
        ]
    except FileNotFoundError:
        log.error(f"Error: Directory '{directory}' not found.")
        return []
    except PermissionError:
        log.error(f"Error: Permission denied for directory '{directory}'.")
        return []


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version numbers based only on the first three parts.

    :param version1: First version number as a string (e.g., "1.2.3").
    :param version2: Second version number as a string (e.g., "1.2.4").
    :return: -1 if version1 < version2, 1 if version1 > version2, 0 if equal.
    """

    def parse_version(version: str) -> List:
        parts = version.split(".")[:3]  # Only consider the first three parts
        parsed_parts = []
        for part in parts:
            if part.isdigit():
                parsed_parts.append(int(part))
            else:
                parsed_parts.append(part)
        return parsed_parts

    v1_parts = parse_version(version1)
    v2_parts = parse_version(version2)

    # Ensure both lists have the same length by padding with zeros
    max_length = 3  # Limit to three parts
    v1_parts.extend([0] * (max_length - len(v1_parts)))
    v2_parts.extend([0] * (max_length - len(v2_parts)))

    # Compare corresponding parts
    for v1, v2 in zip(v1_parts, v2_parts):
        if isinstance(v1, int) and isinstance(v2, int):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
        else:
            v1, v2 = str(v1), str(v2)
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1

    return 0


def delete_and_create_file(delete_path, create_path):
    """
    删除指定的文件，并创建一个新的文件
    :param delete_path: 需要删除的文件路径
    :param create_path: 需要创建的新文件路径
    """
    try:
        # 如果文件存在，先删除
        if os.path.exists(delete_path):
            os.remove(delete_path)

        # 创建新文件
        test = DefaultConfig()
        test.load_default_values()
        test.save_config(create_path)
    except Exception as e:
        log.error(f"操作失败: {e}")
