import json
from pathlib import Path
from typing import List, Optional

from .models import Snapshot, Branch


class RepositoryError(Exception):
    pass


class Repository:
    VC_DIR = ".comfyvc"
    SNAPSHOTS_DIR = "snapshots"
    META_FILE = "meta.json"
    DEFAULT_BRANCH = "main"

    def __init__(self, path: str):
        self.path = Path(path)
        self.vc_dir = self.path / self.VC_DIR
        self.snapshots_dir = self.vc_dir / self.SNAPSHOTS_DIR
        self.meta_file = self.vc_dir / self.META_FILE

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        self.vc_dir.mkdir(exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
        if not self.meta_file.exists():
            self._write_meta({
                "current_branch": self.DEFAULT_BRANCH,
                "branches": {
                    self.DEFAULT_BRANCH: Branch(name=self.DEFAULT_BRANCH).to_dict()
                },
            })

    def is_initialized(self) -> bool:
        return self.vc_dir.exists() and self.meta_file.exists()

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def take_snapshot(self, workflow_path: str, message: str) -> Snapshot:
        self._ensure_initialized()
        workflow = self._load_workflow(workflow_path)
        meta = self._read_meta()
        branch_name = meta["current_branch"]
        branch = Branch.from_dict(meta["branches"][branch_name])

        snapshot = Snapshot.create(
            message=message,
            branch=branch_name,
            workflow=workflow,
            parent_id=branch.head,
        )

        (self.snapshots_dir / f"{snapshot.id}.json").write_text(
            json.dumps(snapshot.to_dict(), indent=2)
        )

        branch.head = snapshot.id
        branch.snapshots.append(snapshot.id)
        meta["branches"][branch_name] = branch.to_dict()
        self._write_meta(meta)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Snapshot:
        f = self.snapshots_dir / f"{snapshot_id}.json"
        if not f.exists():
            raise RepositoryError(f"Snapshot {snapshot_id} not found")
        return Snapshot.from_dict(json.loads(f.read_text()))

    def get_snapshots(self, branch_name: Optional[str] = None) -> List[Snapshot]:
        self._ensure_initialized()
        meta = self._read_meta()
        branch_name = branch_name or meta["current_branch"]
        if branch_name not in meta["branches"]:
            raise RepositoryError(f"Branch '{branch_name}' not found")
        branch = Branch.from_dict(meta["branches"][branch_name])
        results = []
        for sid in reversed(branch.snapshots):
            try:
                results.append(self.get_snapshot(sid))
            except RepositoryError:
                continue
        return results

    def restore(self, snapshot_id: str, target_path: str) -> None:
        snapshot = self.get_snapshot(snapshot_id)
        Path(target_path).write_text(json.dumps(snapshot.workflow, indent=2))

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------

    def create_branch(self, name: str, from_snapshot_id: Optional[str] = None) -> Branch:
        self._ensure_initialized()
        meta = self._read_meta()
        if name in meta["branches"]:
            raise RepositoryError(f"Branch '{name}' already exists")

        if from_snapshot_id is None:
            current = Branch.from_dict(meta["branches"][meta["current_branch"]])
            from_snapshot_id = current.head

        branch = Branch(
            name=name,
            head=from_snapshot_id,
            snapshots=[from_snapshot_id] if from_snapshot_id else [],
        )
        meta["branches"][name] = branch.to_dict()
        self._write_meta(meta)
        return branch

    def switch_branch(self, name: str) -> None:
        self._ensure_initialized()
        meta = self._read_meta()
        if name not in meta["branches"]:
            raise RepositoryError(f"Branch '{name}' not found")
        meta["current_branch"] = name
        self._write_meta(meta)

    def delete_branch(self, name: str) -> None:
        self._ensure_initialized()
        meta = self._read_meta()
        if name == self.DEFAULT_BRANCH:
            raise RepositoryError("Cannot delete the main branch")
        if name == meta["current_branch"]:
            raise RepositoryError("Cannot delete the active branch — switch first")
        if name not in meta["branches"]:
            raise RepositoryError(f"Branch '{name}' not found")
        del meta["branches"][name]
        self._write_meta(meta)

    def get_branches(self) -> List[Branch]:
        self._ensure_initialized()
        meta = self._read_meta()
        return [Branch.from_dict(b) for b in meta["branches"].values()]

    def get_current_branch(self) -> str:
        return self._read_meta()["current_branch"]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self.is_initialized():
            raise RepositoryError("No repository found. Open a workflow file first.")

    def _read_meta(self) -> dict:
        return json.loads(self.meta_file.read_text())

    def _write_meta(self, meta: dict) -> None:
        self.meta_file.write_text(json.dumps(meta, indent=2))

    def _load_workflow(self, workflow_path: str) -> dict:
        p = Path(workflow_path)
        if not p.exists():
            raise RepositoryError(f"Workflow file not found: {workflow_path}")
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError as e:
            raise RepositoryError(f"Invalid workflow JSON: {e}")
