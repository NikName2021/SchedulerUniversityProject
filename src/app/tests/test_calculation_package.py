import io
import json
import zipfile

import pytest
from services.calculation_package import (
    PackageValidationError,
    create_result_archive,
    create_task_archive,
    read_result_archive,
    read_task_archive,
)


def _task_payload() -> dict:
    return {
        "job_uuid": "1b96ad85-55f7-4b06-8834-16d256237f86",
        "context": {"start_date": "2026-09-07", "end_date": "2026-09-07"},
        "components": [],
    }


def test_task_package_round_trip_adds_verified_input_hash() -> None:
    archive = create_task_archive([_task_payload()])

    manifest, jobs = read_task_archive(archive.getvalue())

    assert manifest["format"] == "smart-scheduler-task"
    assert jobs[0]["job_uuid"] == _task_payload()["job_uuid"]
    assert len(jobs[0]["input_sha256"]) == 64


def test_result_package_round_trip() -> None:
    result = {
        "job_uuid": _task_payload()["job_uuid"],
        "input_sha256": "a" * 64,
        "component_results": [],
        "room_assignments": [],
    }

    archive = create_result_archive([result])
    manifest, jobs = read_result_archive(archive.getvalue())

    assert manifest["format"] == "smart-scheduler-result"
    assert jobs == [result]


def test_package_rejects_payload_tampering() -> None:
    source = create_task_archive([_task_payload()]).getvalue()
    tampered = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(source)) as original,
        zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as changed,
    ):
        for name in original.namelist():
            content = original.read(name)
            if name.startswith("jobs/"):
                payload = json.loads(content)
                payload["context"]["end_date"] = "2030-01-01"
                content = json.dumps(payload).encode()
            changed.writestr(name, content)

    with pytest.raises(PackageValidationError, match="hash mismatch"):
        read_task_archive(tampered.getvalue())


def test_package_rejects_unexpected_files() -> None:
    source = create_task_archive([_task_payload()]).getvalue()
    changed = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(source)) as original,
        zipfile.ZipFile(changed, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for name in original.namelist():
            output.writestr(name, original.read(name))
        output.writestr("unexpected.txt", b"not allowed")

    with pytest.raises(PackageValidationError, match="unexpected files"):
        read_task_archive(changed.getvalue())
