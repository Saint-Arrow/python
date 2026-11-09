# -*- coding: utf-8 -*-
"""测试项注册表：新脚本放入 tests/ 目录即被自动发现，无需改平台代码。"""

import hashlib
import importlib
import importlib.util
import json
import logging
import os
import pkgutil
import sys
from typing import Dict, List, Optional, Type

from .base import TestCase

logger = logging.getLogger(__name__)

_REGISTRY: Dict[str, Type[TestCase]] = {}


def register(cls: Type[TestCase]) -> Type[TestCase]:
    """类装饰器：把 TestCase 子类登记进注册表。"""
    if not cls.id:
        raise ValueError(f"{cls.__name__} 缺少 id 属性")
    if cls.id in _REGISTRY:
        raise KeyError(f"测试项 id 重复: {cls.id}")
    _REGISTRY[cls.id] = cls
    return cls


def all_cases() -> Dict[str, Type[TestCase]]:
    """返回全部已注册测试项 {id: class}。"""
    return dict(_REGISTRY)


def get_case_class(case_id: str) -> Optional[Type[TestCase]]:
    return _REGISTRY.get(case_id)


def create(case_id: str, params: Optional[dict] = None) -> Optional[TestCase]:
    cls = _REGISTRY.get(case_id)
    if cls is None:
        return None
    return cls(params)


def discover(package: str = "tests") -> int:
    """自动扫描 tests 包下所有模块，触发 @register 装饰器执行。

    带 import 错误的模块（如缺依赖）只记日志，不影响其他测试项。
    """
    count_before = len(_REGISTRY)
    try:
        pkg = importlib.import_module(package)
    except ImportError as e:
        logger.warning("无法导入测试项包 %s: %s", package, e)
        return 0

    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return 0

    for m in pkgutil.iter_modules(pkg_path):
        if m.name.startswith("_"):
            continue
        mod_name = f"{package}.{m.name}"
        try:
            importlib.import_module(mod_name)
        except Exception as e:  # 缺第三方依赖等情况
            logger.warning("加载测试项模块失败 %s: %s", mod_name, e)
    return len(_REGISTRY) - count_before


# 平台根目录（registry.py 位于 core/ 下）
PLATFORM_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def discover_files(paths: List[str], base_dir: Optional[str] = None) -> int:
    """按文件路径加载外部"脚本即插件"（可指向 net/ 等平台外任意目录）。

    适用于"原脚本原地重构、不搬家"的接入方式：
    - 脚本顶层只允许定义（class/函数），import 时无副作用；
    - 单个脚本加载失败（缺依赖、id 冲突等）只记日志，不影响其他脚本；
    - base_dir 为相对路径的解析基准，默认平台根目录。
    """
    base = base_dir or PLATFORM_ROOT
    if PLATFORM_ROOT not in sys.path:
        sys.path.insert(0, PLATFORM_ROOT)  # 外部脚本 `from core...` 依赖此路径
    before = len(_REGISTRY)
    for p in paths:
        full = p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
        if not os.path.isfile(full):
            logger.warning("插件脚本不存在: %s", full)
            continue
        # 以路径哈希做模块名：同名文件不冲突，重复加载直接跳过
        key = "ext_" + hashlib.md5(full.encode("utf-8")).hexdigest()[:8]
        if key in sys.modules:
            continue
        try:
            spec = importlib.util.spec_from_file_location(key, full)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[key] = mod
            spec.loader.exec_module(mod)
        except Exception as e:  # noqa: BLE001 单文件失败不拖垮整体
            sys.modules.pop(key, None)
            logger.warning("加载插件脚本失败 %s: %s", full, e)
    return len(_REGISTRY) - before


def discover_from_config(config_path: Optional[str] = None) -> int:
    """读取 platform.json 的 "plugins" 列表并加载其中登记的外部脚本。"""
    cfg = config_path or os.path.join(PLATFORM_ROOT, "platform.json")
    if not os.path.isfile(cfg):
        return 0
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.warning("读取插件配置失败 %s: %s", cfg, e)
        return 0
    return discover_files(data.get("plugins", []))
