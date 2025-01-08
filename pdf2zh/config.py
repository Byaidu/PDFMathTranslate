import json
from pathlib import Path
from threading import Lock
import os

class ConfigManager:
    _instance = None
    _lock = Lock()  # 用于线程安全

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return  # 防止重复初始化
        self._initialized = True
        self._config_path = Path.home() / ".config" / "PDFMathTranslate" / "config.json"
        self._config_data = {}
        self._ensure_config_exists()

    def _ensure_config_exists(self, isInit=True):
        """确保配置文件存在，如果不存在则创建默认配置"""
        if not self._config_path.exists():
            if isInit:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                self._config_data = {}  # 默认配置内容
                self._save_config()
            else:
                raise ValueError(f"config file {self._config_path} not found!")
        else:
            self._load_config()

    def _load_config(self):
        """从config.json中加载配置"""
        with self._config_path.open("r", encoding="utf-8") as f:
            self._config_data = json.load(f)

    def _save_config(self):
        """保存配置到config.json"""
        with self._config_path.open("w", encoding="utf-8") as f:
            json.dump(self._config_data, f, indent=4, ensure_ascii=False)

    @classmethod
    def custome_config(cls, file_path):
        """使用自定义路径加载配置文件"""
        custom_path = Path(file_path)
        if not custom_path.exists():
            raise ValueError(f"Config file {custom_path} not found!")
        # 销毁现有的实例并重新初始化
        with cls._lock:
            instance = cls()
            instance._config_path = custom_path
            instance._ensure_config_exists(isInit=False)
            cls._instance = instance

    @classmethod
    def get(cls, key, default=None):
        """获取配置值"""
        instance = cls.get_instance()
        ret = instance._config_data.get(key)
        if not ret:
            env_get = os.environ.get(key)
            if not env_get:
                if not default:
                    raise ValueError(f"{key} is not found in environment or config file.")
                else:
                    instance._config_data[key] = default
                    instance._save_config()
                    return default
            else:
                instance._config_data[key] = env_get
                instance._save_config()
                return env_get
        else:
            return ret

    @classmethod
    def set(cls, key, value):
        """设置配置值并保存"""
        instance = cls.get_instance()
        instance._config_data[key] = value
        instance._save_config()

    @classmethod
    def get_translator_by_name(cls, name):
        """根据 name 获取对应的 translator 配置"""
        instance = cls.get_instance()
        translators = instance._config_data.get("translators", [])
        for translator in translators:
            if translator.get("name") == name:
                return translator
        return None
    
    @classmethod
    def set_translator_by_name(cls, name, new_translator_envs):
        """根据 name 设置或更新 translator 配置"""
        instance = cls.get_instance()
        translators = instance._config_data.get("translators", [])
        
        for translator in translators:
            if translator.get("name") == name:
                translator.update({"envs": new_translator_envs})
                instance._save_config()
                return
        
        # 如果未找到匹配的 name，则添加新的 translator
        translators.append({"name": name, "envs": new_translator_envs})
        instance._config_data["translators"] = translators
        instance._save_config()


    @classmethod
    def delete(cls, key):
        """删除配置值并保存"""
        instance = cls.get_instance()
        if key in instance._config_data:
            del instance._config_data[key]
            instance._save_config()

    @classmethod
    def all(cls):
        """返回所有配置项"""
        instance = cls.get_instance()
        return instance._config_data

# 使用示例
# 默认路径加载
# ConfigManager.set("username", "admin")
# print(ConfigManager.get("username"))

# 自定义路径加载
# ConfigManager.custome_config("/path/to/custom_config.json")
# print(ConfigManager.get("custom_key"))
