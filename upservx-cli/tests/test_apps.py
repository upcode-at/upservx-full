"""CLI contract tests for App Store installation and updates."""

from types import SimpleNamespace

from cli.commands import apps


class RecordingClient:
    def __init__(self) -> None:
        self.calls = []

    def post(self, path, body):
        self.calls.append((path, body))
        return {"message": "complete"}


def test_install_sends_custom_name_and_environment(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(apps, "get_client", lambda: client)

    result = apps.cmd_install(
        SimpleNamespace(
            app="wordpress",
            name="customer-blog",
            env=["SITE_URL=https://example.test", "PASSWORD=a=b"],
        )
    )

    assert result == 0
    assert client.calls == [
        (
            "/containers/app-store/apps/wordpress/install",
            {
                "custom_name": "customer-blog",
                "environment": {
                    "SITE_URL": "https://example.test",
                    "PASSWORD": "a=b",
                },
            },
        )
    ]


def test_install_rejects_malformed_environment_assignment(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(apps, "get_client", lambda: client)

    result = apps.cmd_install(
        SimpleNamespace(app="wordpress", name=None, env=["MISSING_VALUE"])
    )

    assert result == 2
    assert client.calls == []


def test_update_uses_project_name(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(apps, "get_client", lambda: client)

    result = apps.cmd_update(SimpleNamespace(project="customer-blog"))

    assert result == 0
    assert client.calls == [
        ("/containers/app-store/apps/customer-blog/update", {})
    ]
