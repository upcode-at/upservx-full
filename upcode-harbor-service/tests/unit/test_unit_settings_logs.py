from pathlib import Path

from handlers import settings


def test_read_log_file_supports_nested_relative_paths(tmp_path, monkeypatch):
    log_root = tmp_path / "var" / "log"
    activity_log = log_root / "upcode-harbor" / "activity.log"
    activity_log.parent.mkdir(parents=True)
    activity_log.write_text("nested log entry\n", encoding="utf-8")

    monkeypatch.setattr(settings, "LOG_DIR", str(log_root))

    assert settings.read_log_file("upcode-harbor/activity.log", lines=0) == "nested log entry\n"


def test_read_log_file_supports_absolute_paths_within_log_root(tmp_path, monkeypatch):
    log_root = tmp_path / "var" / "log"
    activity_log = log_root / "upcode-harbor" / "activity.log"
    activity_log.parent.mkdir(parents=True)
    activity_log.write_text("absolute path entry\n", encoding="utf-8")

    monkeypatch.setattr(settings, "LOG_DIR", str(log_root))

    assert settings.read_log_file(str(activity_log), lines=0) == "absolute path entry\n"


def test_get_log_files_includes_nested_activity_log(tmp_path, monkeypatch):
    log_root = tmp_path / "var" / "log"
    top_level_log = log_root / "syslog"
    activity_log = log_root / "upcode-harbor" / "activity.log"
    activity_log.parent.mkdir(parents=True)
    top_level_log.write_text("system\n", encoding="utf-8")
    activity_log.write_text("activity\n", encoding="utf-8")

    monkeypatch.setattr(settings, "LOG_DIR", str(log_root))

    logs = settings.get_log_files()
    names = {entry["name"] for entry in logs}

    assert "syslog" in names
    assert "upcode-harbor/activity.log" in names