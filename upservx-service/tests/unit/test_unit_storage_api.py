"""Regression tests for storage API request-to-handler mappings."""

from unittest.mock import patch

from api.storage import api_format_drive, api_mount_drive, api_unmount_drive
from lib.models import DriveFormatRequest, DriveMountRequest, DriveUnmountRequest


def test_mount_uses_request_mountpoint():
    payload = DriveMountRequest(device="/dev/sdb1", mountpoint="/mnt/data")

    with patch("api.storage.mount_drive") as mount_drive:
        result = api_mount_drive(payload)

    mount_drive.assert_called_once_with("/dev/sdb1", "/mnt/data")
    assert result == {"detail": "mounted"}


def test_unmount_passes_device_and_mountpoint():
    payload = DriveUnmountRequest(device="/dev/sdb1", mountpoint="/mnt/data")

    with patch("api.storage.unmount_drive") as unmount_drive:
        result = api_unmount_drive(payload)

    unmount_drive.assert_called_once_with(
        device="/dev/sdb1",
        mountpoint="/mnt/data",
    )
    assert result == {"detail": "unmounted"}


def test_format_uses_request_filesystem():
    payload = DriveFormatRequest(
        device="/dev/sdb1",
        filesystem="ext4",
        label="data",
    )

    with patch("api.storage.format_drive") as format_drive:
        result = api_format_drive(payload)

    format_drive.assert_called_once_with("/dev/sdb1", "ext4", "data")
    assert result == {"detail": "formatted"}
