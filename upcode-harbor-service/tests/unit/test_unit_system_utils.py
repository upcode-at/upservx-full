"""
Unit tests for lib/system_utils.py
===================================
Tests helper functions for system analysis in isolation – without real system access.
External calls (subprocess, psutil, /proc/…) are mocked.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock, mock_open


# ---------------------------------------------------------------------------
# Stub: psutil (may be unavailable in CI without hardware)
# ---------------------------------------------------------------------------
_psutil_stub = types.ModuleType("psutil")
_psutil_stub.net_io_counters = MagicMock(return_value=MagicMock(bytes_sent=0, bytes_recv=0))
_psutil_stub.cpu_percent = MagicMock(return_value=5.0)
_psutil_stub.virtual_memory = MagicMock(return_value=MagicMock(total=8*1024**3, used=2*1024**3, percent=25.0))
_psutil_stub.process_iter = MagicMock(return_value=iter([]))
_psutil_stub.boot_time = MagicMock(return_value=0.0)
sys.modules.setdefault("psutil", _psutil_stub)

from lib.system_utils import format_uptime, get_cpu_model, get_service_status  # noqa: E402


# ---------------------------------------------------------------------------
# format_uptime
# ---------------------------------------------------------------------------

class TestFormatUptime:
    def test_zero_seconds(self):
        assert format_uptime(0) == "0m"

    def test_only_minutes(self):
        assert format_uptime(90) == "1m"

    def test_hours_and_minutes(self):
        assert format_uptime(3661) == "1h 1m"

    def test_days_hours_minutes(self):
        # 1 day, 2 hours, 3 minutes = 86400 + 7200 + 180 = 93780 seconds
        assert format_uptime(93780) == "1d 2h 3m"

    def test_exactly_one_hour(self):
        assert format_uptime(3600) == "1h"

    def test_exactly_one_day(self):
        assert format_uptime(86400) == "1d"

    def test_large_uptime(self):
        # 10 days, 5 hours
        seconds = 10 * 86400 + 5 * 3600
        result = format_uptime(seconds)
        assert "10d" in result
        assert "5h" in result

    def test_returns_string(self):
        assert isinstance(format_uptime(100), str)


# ---------------------------------------------------------------------------
# get_cpu_model
# ---------------------------------------------------------------------------

class TestGetCpuModel:
    def test_returns_platform_processor_when_available(self):
        with patch("lib.system_utils.platform.processor", return_value="Intel Core i7"):
            result = get_cpu_model()
        assert result == "Intel Core i7"

    def test_fallback_to_proc_cpuinfo(self):
        cpuinfo_content = "model name\t: AMD Ryzen 9 5900X\n"
        with (
            patch("lib.system_utils.platform.processor", return_value=""),
            patch("builtins.open", mock_open(read_data=cpuinfo_content)),
        ):
            result = get_cpu_model()
        assert result == "AMD Ryzen 9 5900X"

    def test_returns_unknown_when_all_fail(self):
        with (
            patch("lib.system_utils.platform.processor", return_value=""),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            result = get_cpu_model()
        assert result == "unknown"


# ---------------------------------------------------------------------------
# get_service_status
# ---------------------------------------------------------------------------

class TestGetServiceStatus:
    def test_running_service_via_systemctl(self):
        with (
            patch("lib.system_utils.shutil.which", return_value="/usr/bin/systemctl"),
            patch("lib.system_utils.subprocess.run", return_value=MagicMock(
                returncode=0, stdout="active\n", stderr=""
            )),
        ):
            assert get_service_status("docker") == "running"

    def test_stopped_service_via_systemctl(self):
        with (
            patch("lib.system_utils.shutil.which", return_value="/usr/bin/systemctl"),
            patch("lib.system_utils.subprocess.run", return_value=MagicMock(
                returncode=3, stdout="inactive\n", stderr=""
            )),
        ):
            assert get_service_status("docker") == "stopped"

    def test_not_found_service_via_systemctl(self):
        with (
            patch("lib.system_utils.shutil.which", return_value="/usr/bin/systemctl"),
            patch("lib.system_utils.subprocess.run", return_value=MagicMock(
                returncode=4, stdout="", stderr="could not be found"
            )),
        ):
            assert get_service_status("nonexistent") == "not found"

    def test_not_found_when_binary_missing_no_systemctl(self):
        # kein systemctl, kein Prozess
        with (
            patch("lib.system_utils.shutil.which", return_value=None),
        ):
            assert get_service_status("ghost-service") == "not found"
