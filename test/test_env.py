"""Environment fixes applied when pdf2zh is imported."""

import os
from unittest.mock import patch

import httpx

import pdf2zh


def test_bracketed_ipv6_no_proxy_is_normalized():
    env = {
        "NO_PROXY": "localhost,127.0.0.1,::1,.local,[::1]",
        "no_proxy": "[fe80::1]:8080, example.com",
        "HTTPS_PROXY": "http://127.0.0.1:7897",
    }
    with patch.dict(os.environ, env):
        pdf2zh._normalize_no_proxy()
        assert os.environ["NO_PROXY"] == "localhost,127.0.0.1,::1,.local"
        assert os.environ["no_proxy"] == "fe80::1,example.com"
        # httpx reads the proxy environment when a client is created.
        httpx.Client().close()


def test_plain_no_proxy_is_left_alone():
    with patch.dict(os.environ, {"NO_PROXY": "localhost,.local"}):
        pdf2zh._normalize_no_proxy()
        assert os.environ["NO_PROXY"] == "localhost,.local"
