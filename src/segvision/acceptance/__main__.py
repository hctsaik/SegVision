from __future__ import annotations

import argparse
import json
import sys

from .contracts import validate_contracts
from .evidence import validate_evidence
from .state import validate_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m segvision.acceptance")
    sub = parser.add_subparsers(dest="command", required=True)
    p_contracts = sub.add_parser("validate-contracts")
    p_contracts.add_argument("--change", required=True)
    p_evidence = sub.add_parser("validate-evidence")
    p_evidence.add_argument("--evidence", required=True)
    p_evidence.add_argument("--change", default="openspec/changes/build-segvision-v1")
    p_state = sub.add_parser("validate-state")
    p_state.add_argument("--state")
    p_state.add_argument("--change", default="openspec/changes/build-segvision-v1")
    p_state.add_argument("--evidence")
    p_state.add_argument(
        "--graph", default="openspec/changes/build-segvision-v1/acceptance/task-graph.json"
    )
    p_manifest = sub.add_parser("validate-manifest")
    p_manifest.add_argument("manifest_arg", nargs="?")
    p_manifest.add_argument("--manifest", dest="manifest_opt")
    p_run = sub.add_parser("run")
    p_run.add_argument("--tier", choices=("A", "B", "C"), required=True)
    p_run.add_argument("--manifest", default="openspec/changes/build-segvision-v1/acceptance/e2e-cases.json")
    p_run.add_argument("--profile", default=None)
    p_run.add_argument("--evidence", default="evidence")
    p_verdict = sub.add_parser("verdict")
    p_verdict.add_argument("--evidence", required=True)
    p_verdict.add_argument("--target", choices=("engineering", "domain"), default="engineering")
    p_execute = sub.add_parser("execute")
    p_execute.add_argument("--max-tasks", type=int, default=None)
    p_execute.add_argument("--graph", default="openspec/changes/build-segvision-v1/acceptance/task-graph.json")
    p_execute.add_argument("--state", default="evidence/execution-state.json")
    p_execute.add_argument("--tasks-file", default="openspec/changes/build-segvision-v1/tasks.md")
    p_execute.add_argument("--evidence-root", default="evidence")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-contracts":
            result = validate_contracts(args.change)
        elif args.command == "validate-evidence":
            result = validate_evidence(args.evidence, args.change)
        elif args.command == "validate-state":
            state_path = args.state or (
                f"{args.evidence}/execution-state.json" if args.evidence else "evidence/execution-state.json"
            )
            graph = args.graph
            if args.change and args.change != "openspec/changes/build-segvision-v1":
                graph = f"{args.change}/acceptance/task-graph.json"
            result = validate_state(state_path, graph)
        elif args.command == "run":
            from .runner import run_manifest

            result = run_manifest(
                args.manifest, tier=args.tier, profile=args.profile, output_dir=args.evidence
            )
        elif args.command == "verdict":
            from .release import classify_evidence_directory

            result = classify_evidence_directory(args.evidence, target_release_class=args.target)
        elif args.command == "execute":
            from .controller import TaskController

            result = TaskController(
                graph=args.graph,
                state=args.state,
                tasks_file=args.tasks_file,
                evidence_root=args.evidence_root,
            ).run(max_tasks=args.max_tasks).to_dict()
        else:
            from .runner import validate_manifest

            manifest = args.manifest_opt or args.manifest_arg
            if not manifest:
                raise ValueError("validate-manifest requires a manifest path")
            result = validate_manifest(manifest)
        print(json.dumps(result, sort_keys=True, indent=2, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
