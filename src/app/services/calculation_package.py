from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Literal

TASK_FORMAT = "smart-scheduler-task"
RESULT_FORMAT = "smart-scheduler-result"
SCHEMA_VERSION = 1
MAX_PACKAGE_JOBS = 64
MAX_MANIFEST_BYTES = 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class PackageValidationError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_uuid(value: Any) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PackageValidationError("Package contains an invalid job UUID") from exc
    canonical = str(parsed)
    if str(value) != canonical:
        raise PackageValidationError("Job UUID must use canonical lowercase form")
    return canonical


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_archive(
    package_format: Literal["smart-scheduler-task", "smart-scheduler-result"],
    jobs: list[dict[str, Any]],
) -> io.BytesIO:
    if not 1 <= len(jobs) <= MAX_PACKAGE_JOBS:
        raise PackageValidationError(
            f"A package must contain between 1 and {MAX_PACKAGE_JOBS} jobs"
        )

    descriptors: list[dict[str, Any]] = []
    members: list[tuple[str, bytes]] = []
    seen_uuids: set[str] = set()
    for payload in jobs:
        job_uuid = _canonical_uuid(payload.get("job_uuid"))
        if job_uuid in seen_uuids:
            raise PackageValidationError("Package contains duplicate job UUIDs")
        seen_uuids.add(job_uuid)
        encoded = canonical_json_bytes(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        descriptor: dict[str, Any] = {
            "job_uuid": job_uuid,
            "sha256": digest,
        }
        if package_format == RESULT_FORMAT:
            input_sha256 = payload.get("input_sha256")
            if not _is_sha256(input_sha256):
                raise PackageValidationError("Result contains an invalid input hash")
            descriptor["input_sha256"] = input_sha256
        descriptors.append(descriptor)
        members.append((f"jobs/{job_uuid}.json", encoded))

    manifest = {
        "format": package_format,
        "schema_version": SCHEMA_VERSION,
        "created_at": _created_at(),
        "jobs": descriptors,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        archive.writestr("manifest.json", canonical_json_bytes(manifest))
        for filename, encoded in members:
            archive.writestr(filename, encoded)
    output.seek(0)
    return output


def create_task_archive(jobs: list[dict[str, Any]]) -> io.BytesIO:
    return _create_archive(TASK_FORMAT, jobs)


def create_result_archive(jobs: list[dict[str, Any]]) -> io.BytesIO:
    return _create_archive(RESULT_FORMAT, jobs)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _load_json(raw: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number: {value}")

    try:
        decoded = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as exc:
        raise PackageValidationError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise PackageValidationError(f"{label} must contain a JSON object")
    return decoded


def read_package(
    content: bytes,
    *,
    expected_format: Literal["smart-scheduler-task", "smart-scheduler-result"],
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content), mode="r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise PackageValidationError("File is not a valid calculation package") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_PACKAGE_JOBS + 1:
            raise PackageValidationError("Package contains too many files")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise PackageValidationError("Package contains duplicate file names")
        if any(info.is_dir() or info.flag_bits & 0x1 for info in infos):
            raise PackageValidationError(
                "Package must not contain directories or encrypted files"
            )
        if any(
            info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            for info in infos
        ):
            raise PackageValidationError("Package uses an unsupported compression type")
        if sum(info.file_size for info in infos) > max_uncompressed_bytes:
            raise PackageValidationError("Uncompressed package is too large")
        if "manifest.json" not in names:
            raise PackageValidationError("Package manifest is missing")
        manifest_info = archive.getinfo("manifest.json")
        if manifest_info.file_size > MAX_MANIFEST_BYTES:
            raise PackageValidationError("Package manifest is too large")
        manifest = _load_json(archive.read(manifest_info), label="Package manifest")

        if manifest.get("format") != expected_format:
            raise PackageValidationError("Unexpected calculation package type")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise PackageValidationError(
                f"Unsupported package schema version: {manifest.get('schema_version')}"
            )
        descriptors = manifest.get("jobs")
        if (
            not isinstance(descriptors, list)
            or not 1 <= len(descriptors) <= MAX_PACKAGE_JOBS
        ):
            raise PackageValidationError("Package contains an invalid job list")

        expected_names = {"manifest.json"}
        jobs: list[dict[str, Any]] = []
        seen_uuids: set[str] = set()
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                raise PackageValidationError("Package job descriptor is invalid")
            job_uuid = _canonical_uuid(descriptor.get("job_uuid"))
            if job_uuid in seen_uuids:
                raise PackageValidationError("Package contains duplicate job UUIDs")
            seen_uuids.add(job_uuid)
            filename = f"jobs/{job_uuid}.json"
            expected_names.add(filename)
            if filename not in names:
                raise PackageValidationError(f"Payload for job {job_uuid} is missing")
            raw_payload = archive.read(filename)
            digest = hashlib.sha256(raw_payload).hexdigest()
            if digest != descriptor.get("sha256"):
                raise PackageValidationError(
                    f"Payload hash mismatch for job {job_uuid}"
                )
            payload = _load_json(raw_payload, label=f"Payload for job {job_uuid}")
            if payload.get("job_uuid") != job_uuid:
                raise PackageValidationError(
                    "Payload UUID does not match its descriptor"
                )
            if expected_format == RESULT_FORMAT:
                input_sha256 = descriptor.get("input_sha256")
                if not _is_sha256(input_sha256):
                    raise PackageValidationError(
                        "Result descriptor has an invalid input hash"
                    )
                if payload.get("input_sha256") != input_sha256:
                    raise PackageValidationError(
                        "Result input hash does not match its descriptor"
                    )
            else:
                # Expose the verified digest to the local solver without making
                # the payload hash recursively depend on itself.
                payload["input_sha256"] = digest
            jobs.append(payload)

        if set(names) != expected_names:
            raise PackageValidationError("Package contains unexpected files")
        return manifest, jobs


def read_task_archive(
    content: bytes, *, max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        return read_package(
            content,
            expected_format=TASK_FORMAT,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        raise PackageValidationError("Calculation package is corrupted") from exc


def read_result_archive(
    content: bytes, *, max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        return read_package(
            content,
            expected_format=RESULT_FORMAT,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        raise PackageValidationError("Calculation package is corrupted") from exc
