from unittest.mock import patch


class TestLogsApi:
    def test_activity_log_reads_upservx_activity_file(self, client, api_key_headers):
        with patch("api.logs.read_log_file", return_value="activity entry\n") as read_log_file:
            resp = client.get("/logs/activity", headers=api_key_headers)

        assert resp.status_code == 200
        assert resp.json()["content"] == "activity entry\n"
        read_log_file.assert_called_once_with("/var/log/upservx/activity.log", lines=100)

    def test_activity_log_accepts_lines_query(self, client, api_key_headers):
        with patch("api.logs.read_log_file", return_value="activity entry\n") as read_log_file:
            resp = client.get("/logs/activity?lines=25", headers=api_key_headers)

        assert resp.status_code == 200
        read_log_file.assert_called_once_with("/var/log/upservx/activity.log", lines=25)

    def test_legacy_activity_log_route_still_works(self, client, api_key_headers):
        with patch("api.logs.read_log_file", return_value="activity entry\n") as read_log_file:
            resp = client.get("/activity-log", headers=api_key_headers)

        assert resp.status_code == 200
        read_log_file.assert_called_once_with("/var/log/upservx/activity.log", lines=100)