import json
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

from comfyvc.repository import Repository, RepositoryError
from comfyvc.models import Snapshot, Branch
from comfyvc.diff import diff_snapshots

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

WORKFLOW_A = {
    "nodes": [
        {"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["v1-5-pruned.ckpt"]},
        {"id": 2, "type": "CLIPTextEncode", "widgets_values": ["a cat"]},
    ],
    "links": [[1, 1, 0, 2, 0, "CLIP"]],
}

WORKFLOW_B = {
    "nodes": [
        {"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["dreamshaper.ckpt"]},  # modified
        {"id": 3, "type": "KSampler", "widgets_values": [42, 20, 7.0]},                        # added
    ],
    # node 2 removed; link 1 removed
    "links": [],
}


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def workflow_file(tmp_dir):
    f = tmp_dir / "test_workflow.json"
    f.write_text(json.dumps(WORKFLOW_A))
    return f


@pytest.fixture
def repo(tmp_dir):
    r = Repository(str(tmp_dir))
    r.init()
    return r


# ------------------------------------------------------------------
# Repository — init
# ------------------------------------------------------------------

class TestRepositoryInit:
    def test_init_creates_vc_dir(self, tmp_dir):
        r = Repository(str(tmp_dir))
        r.init()
        assert (tmp_dir / ".comfyvc").exists()
        assert (tmp_dir / ".comfyvc" / "snapshots").exists()
        assert (tmp_dir / ".comfyvc" / "meta.json").exists()

    def test_init_idempotent(self, repo):
        repo.init()  # second call should not raise
        assert repo.is_initialized()

    def test_default_branch_is_main(self, repo):
        assert repo.get_current_branch() == "main"


# ------------------------------------------------------------------
# Repository — snapshots
# ------------------------------------------------------------------

class TestSnapshots:
    def test_take_snapshot_returns_snapshot(self, repo, workflow_file):
        snap = repo.take_snapshot(str(workflow_file), "initial commit")
        assert snap.message == "initial commit"
        assert snap.branch == "main"
        assert snap.workflow == WORKFLOW_A

    def test_take_snapshot_persists_to_disk(self, repo, workflow_file):
        snap = repo.take_snapshot(str(workflow_file), "first")
        loaded = repo.get_snapshot(snap.id)
        assert loaded.id == snap.id
        assert loaded.message == "first"

    def test_get_snapshots_newest_first(self, repo, workflow_file):
        s1 = repo.take_snapshot(str(workflow_file), "first")
        s2 = repo.take_snapshot(str(workflow_file), "second")
        snaps = repo.get_snapshots()
        assert snaps[0].id == s2.id
        assert snaps[1].id == s1.id

    def test_get_snapshot_missing_raises(self, repo):
        with pytest.raises(RepositoryError):
            repo.get_snapshot("nonexistent-id")

    def test_restore_writes_workflow(self, repo, workflow_file, tmp_dir):
        snap = repo.take_snapshot(str(workflow_file), "v1")
        # Overwrite original
        workflow_file.write_text(json.dumps(WORKFLOW_B))
        # Restore
        repo.restore(snap.id, str(workflow_file))
        restored = json.loads(workflow_file.read_text())
        assert restored == WORKFLOW_A

    def test_snapshot_parent_chain(self, repo, workflow_file):
        s1 = repo.take_snapshot(str(workflow_file), "first")
        s2 = repo.take_snapshot(str(workflow_file), "second")
        assert s2.parent_id == s1.id
        assert s1.parent_id is None


# ------------------------------------------------------------------
# Repository — branches
# ------------------------------------------------------------------

class TestBranches:
    def test_create_branch(self, repo, workflow_file):
        repo.take_snapshot(str(workflow_file), "base")
        branch = repo.create_branch("feature")
        assert branch.name == "feature"

    def test_create_duplicate_branch_raises(self, repo):
        with pytest.raises(RepositoryError, match="already exists"):
            repo.create_branch("main")

    def test_switch_branch(self, repo, workflow_file):
        repo.take_snapshot(str(workflow_file), "base")
        repo.create_branch("feature")
        repo.switch_branch("feature")
        assert repo.get_current_branch() == "feature"

    def test_switch_nonexistent_branch_raises(self, repo):
        with pytest.raises(RepositoryError):
            repo.switch_branch("ghost")

    def test_delete_branch(self, repo, workflow_file):
        repo.take_snapshot(str(workflow_file), "base")
        repo.create_branch("temp")
        repo.delete_branch("temp")
        branches = [b.name for b in repo.get_branches()]
        assert "temp" not in branches

    def test_delete_main_branch_raises(self, repo):
        with pytest.raises(RepositoryError):
            repo.delete_branch("main")

    def test_delete_active_branch_raises(self, repo, workflow_file):
        repo.take_snapshot(str(workflow_file), "base")
        repo.create_branch("active")
        repo.switch_branch("active")
        with pytest.raises(RepositoryError):
            repo.delete_branch("active")

    def test_snapshots_isolated_per_branch(self, repo, workflow_file):
        repo.take_snapshot(str(workflow_file), "on main")
        repo.create_branch("feature")
        repo.switch_branch("feature")
        repo.take_snapshot(str(workflow_file), "on feature")

        main_snaps = [s.message for s in repo.get_snapshots("main")]
        feature_snaps = [s.message for s in repo.get_snapshots("feature")]

        assert "on main" in main_snaps
        assert "on feature" not in main_snaps
        assert "on feature" in feature_snaps


# ------------------------------------------------------------------
# Diff engine
# ------------------------------------------------------------------

class TestDiff:
    def _make_snapshot(self, workflow, branch="main") -> Snapshot:
        return Snapshot.create("test", branch, workflow)

    def test_identical_snapshots_no_changes(self):
        s = self._make_snapshot(WORKFLOW_A)
        result = diff_snapshots(s, s)
        assert not result.has_changes
        assert result.summary == "Identical"

    def test_detects_added_node(self):
        a = self._make_snapshot(WORKFLOW_A)
        b = self._make_snapshot(WORKFLOW_B)
        result = diff_snapshots(a, b)
        added_ids = [n.get("id") for n in result.added_nodes]
        assert 3 in added_ids

    def test_detects_removed_node(self):
        a = self._make_snapshot(WORKFLOW_A)
        b = self._make_snapshot(WORKFLOW_B)
        result = diff_snapshots(a, b)
        removed_ids = [n.get("id") for n in result.removed_nodes]
        assert 2 in removed_ids

    def test_detects_modified_node(self):
        a = self._make_snapshot(WORKFLOW_A)
        b = self._make_snapshot(WORKFLOW_B)
        result = diff_snapshots(a, b)
        modified_ids = [n.node_id for n in result.modified_nodes]
        assert 1 in modified_ids

    def test_detects_removed_links(self):
        a = self._make_snapshot(WORKFLOW_A)
        b = self._make_snapshot(WORKFLOW_B)
        result = diff_snapshots(a, b)
        assert len(result.removed_links) == 1

    def test_summary_string(self):
        a = self._make_snapshot(WORKFLOW_A)
        b = self._make_snapshot(WORKFLOW_B)
        result = diff_snapshots(a, b)
        assert "node" in result.summary
