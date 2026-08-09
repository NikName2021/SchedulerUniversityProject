from __future__ import annotations

import argparse
import concurrent.futures
import copy
import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any

from services.calculation_package import (
    PackageValidationError,
    create_result_archive,
    read_task_archive,
)
from services.scalable_scheduler import assign_rooms_matching, solve_event_component

MAX_LOCAL_PACKAGE_BYTES = 100 * 1024 * 1024


def _solve_component(
    item: tuple[str, list[dict[str, Any]], dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    component_key, events, context = item
    return component_key, solve_event_component(events, context)


def solve_task_jobs(
    jobs: list[dict[str, Any]],
    *,
    component_workers: int,
    solver_workers: int,
) -> list[dict[str, Any]]:
    if not 1 <= component_workers <= 64 or not 1 <= solver_workers <= 64:
        raise ValueError("Worker counts must be between 1 and 64")

    work_items: list[tuple[str, str, list[dict[str, Any]], dict[str, Any]]] = []
    jobs_by_uuid: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_uuid = str(job.get("job_uuid", ""))
        context = job.get("context")
        components = job.get("components")
        if (
            not job_uuid
            or not isinstance(context, dict)
            or not isinstance(components, list)
        ):
            raise PackageValidationError("Task payload has an invalid structure")
        if job_uuid in jobs_by_uuid:
            raise PackageValidationError("Task package contains duplicate jobs")
        jobs_by_uuid[job_uuid] = job
        local_context = copy.deepcopy(context)
        local_context["num_workers"] = solver_workers
        for component in components:
            if not isinstance(component, dict):
                raise PackageValidationError("Task component is invalid")
            component_key = component.get("component_key")
            events = component.get("events")
            if not isinstance(component_key, str) or not isinstance(events, list):
                raise PackageValidationError("Task component has an invalid structure")
            work_items.append((job_uuid, component_key, events, local_context))

    solved: dict[str, list[dict[str, Any]]] = {
        job_uuid: [] for job_uuid in jobs_by_uuid
    }
    process_items = [
        (component_key, events, context)
        for _job_uuid, component_key, events, context in work_items
    ]
    if component_workers == 1:
        solved_items = map(_solve_component, process_items)
        for (job_uuid, _key, _events, _context), (component_key, result) in zip(
            work_items, solved_items
        ):
            solved[job_uuid].append({"component_key": component_key, "result": result})
    else:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=component_workers
        ) as executor:
            for (job_uuid, _key, _events, _context), (
                component_key,
                result,
            ) in zip(work_items, executor.map(_solve_component, process_items)):
                solved[job_uuid].append(
                    {"component_key": component_key, "result": result}
                )

    result_jobs: list[dict[str, Any]] = []
    for job_uuid, job in jobs_by_uuid.items():
        component_results = solved[job_uuid]
        successful = [
            item["result"]
            for item in component_results
            if item["result"].get("status") == "success"
        ]
        assignments = [
            assignment
            for result in successful
            for assignment in result.get("assignments", [])
        ]
        room_context = copy.deepcopy(job["context"])
        room_context["num_workers"] = solver_workers
        room_assignments, room_warnings, room_metrics = assign_rooms_matching(
            assignments, room_context
        )
        result_jobs.append(
            {
                "job_uuid": job_uuid,
                "input_sha256": job["input_sha256"],
                "component_results": component_results,
                "room_assignments": room_assignments,
                "room_warnings": room_warnings,
                "room_metrics": room_metrics,
                "solver": {
                    "engine": "ortools-cp-sat",
                    "ortools_version": importlib.metadata.version("ortools"),
                    "component_workers": component_workers,
                    "solver_workers": solver_workers,
                },
            }
        )
    return result_jobs


def solve_package(
    input_path: Path,
    output_path: Path,
    *,
    component_workers: int,
    solver_workers: int,
) -> None:
    if input_path.suffix.lower() != ".scheduler-task":
        raise PackageValidationError("Input file must use .scheduler-task extension")
    if output_path.suffix.lower() != ".scheduler-result":
        raise PackageValidationError("Output file must use .scheduler-result extension")
    if input_path.stat().st_size > MAX_LOCAL_PACKAGE_BYTES:
        raise PackageValidationError("Task package is too large")

    _manifest, jobs = read_task_archive(input_path.read_bytes())
    results = solve_task_jobs(
        jobs,
        component_workers=component_workers,
        solver_workers=solver_workers,
    )
    archive = create_result_archive(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.write_bytes(archive.getvalue())
    temporary_path.replace(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scheduler-solver",
        description="Solve exported Smart Scheduler tasks without a server database.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    solve_parser = subparsers.add_parser("solve", help="solve a task package")
    solve_parser.add_argument("input", type=Path, help="path to .scheduler-task")
    solve_parser.add_argument(
        "--output", "-o", required=True, type=Path, help="result package path"
    )
    solve_parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, (os.cpu_count() or 2) - 1)),
        help="number of components solved in parallel",
    )
    solve_parser.add_argument(
        "--solver-workers",
        type=int,
        default=1,
        help="OR-Tools threads per component",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "solve":
            solve_package(
                args.input,
                args.output,
                component_workers=args.workers,
                solver_workers=args.solver_workers,
            )
            print(f"Result written to {args.output}")
            return 0
    except (OSError, ValueError, PackageValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
