# -*- coding: utf-8 -*-
"""
统一 HTTP 请求环境配置（requests 封装）
=====================================
功能：
1. 自动代理：默认读取系统代理（HTTP_PROXY/HTTPS_PROXY 环境变量），
   也可通过环境变量 TWIN_HTTP_PROXY 强制指定，如 http://127.0.0.1:65532
2. 超时 + 自动重试：连接类错误自动重试（指数退避）
3. 统一返回：raise_for_status 统一抛错，json() 快捷方法
4. UTF-8 安全：日志输出自动去除 emoji，防止 Windows GBK 控制台报错

用法示例：
    from http_client import http
    r = http.get("https://api.example.com/data", params={"id": 1})
    data = r.json()

    # 需要完全跳过代理时：
    r = http.get(url, proxies={"http": None, "https": None})
"""
import os
import sys
import time
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- 日志（UTF-8 / 无 emoji，Windows 控制台安全） ----------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("twin-http")


def _safe(msg: str) -> str:
    """去掉增补平面字符（emoji），避免 Windows GBK 控制台 UnicodeEncodeError"""
    import re
    return re.sub(r"[\U00010000-\U0010ffff]", "", str(msg))


# ---------- 代理配置 ----------
def _resolve_proxies():
    """
    优先级：
      1. 环境变量 TWIN_HTTP_PROXY / TWIN_HTTPS_PROXY（本项目专用，推荐）
      2. 系统标准环境变量 HTTP_PROXY / HTTPS_PROXY（requests 默认行为）
      3. 都没有则不走代理
    """
    p_http = os.environ.get("TWIN_HTTP_PROXY") or os.environ.get("HTTP_PROXY")
    p_https = os.environ.get("TWIN_HTTPS_PROXY") or os.environ.get("HTTPS_PROXY")
    if p_http or p_https:
        log.info(_safe(f"HTTP 客户端启用代理: http={p_http or '-'} https={p_https or '-'}"))
    return {"http": p_http, "https": p_https} if (p_http or p_https) else None


# ---------- 重试策略 ----------
_RETRY_TOTAL = int(os.environ.get("TWIN_HTTP_RETRIES", "3"))  # 总重试次数
_RETRY_BACKOFF = float(os.environ.get("TWIN_HTTP_BACKOFF", "0.5"))  # 退避基数(秒)

retry_strategy = Retry(
    total=_RETRY_TOTAL,
    connect=_RETRY_TOTAL,
    read=_RETRY_TOTAL,
    backoff_factor=_RETRY_BACKOFF,
    status_forcelist=(429, 500, 502, 503, 504),  # 这些状态码也自动重试
    allowed_methods=("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"),
)


def create_session(timeout_default=30.0) -> requests.Session:
    """
    创建带重试/代理/超时的 Session。
    所有请求默认超时 30 秒，可通过环境变量 TWIN_HTTP_TIMEOUT 覆盖。
    """
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.proxies = _resolve_proxies()
    s.headers.update({
        "User-Agent": "shanghai-bridge-twin/1.0 (+python-requests)",
        "Accept": "application/json, text/plain, */*",
    })
    # 把默认超时挂到 session 上，供 request 包装读取
    s._default_timeout = float(os.environ.get("TWIN_HTTP_TIMEOUT", str(timeout_default)))
    return s


# ---------- 全局单例：项目内直接 from http_client import http ----------
http = create_session()


# ---------- 带超时的便捷封装（requests.Session 原生不带默认超时） ----------
def _with_timeout(kwargs):
    kwargs.setdefault("timeout", getattr(http, "_default_timeout", 30.0))
    return kwargs


def get(url, **kwargs):
    return http.get(url, **_with_timeout(kwargs))


def post(url, **kwargs):
    return http.post(url, **_with_timeout(kwargs))


def put(url, **kwargs):
    return http.put(url, **_with_timeout(kwargs))


def delete(url, **kwargs):
    return http.delete(url, **_with_timeout(kwargs))


def get_json(url, **kwargs):
    """GET 并解析 JSON，失败时抛出带上下文的异常"""
    r = get(url, **kwargs)
    r.raise_for_status()
    return r.json()


def post_json(url, payload=None, **kwargs):
    """POST JSON 并解析响应"""
    r = post(url, json=payload, **kwargs)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    # 自检：访问一个公共接口验证网络环境
    print("=" * 50)
    print("HTTP 环境自检")
    print(f"  代理: {http.proxies or '未启用'}")
    print(f"  超时: {http._default_timeout}s  重试: {_RETRY_TOTAL} 次")
    print("=" * 50)
    try:
        t0 = time.time()
        data = get_json("https://httpbin.org/get")
        log.info(_safe(f"自检通过 ({time.time()-t0:.2f}s), origin={data.get('origin')}"))
    except Exception as e:
        log.error(_safe(f"自检失败: {e}"))
        sys.exit(1)
