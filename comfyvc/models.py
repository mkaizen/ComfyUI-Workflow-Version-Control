from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid


@dataclass
class Snapshot:
    id: str
    message: str
    timestamp: datetime
    branch: str
    workflow: dict
    parent_id: Optional[str] = None

    @classmethod
    def create(cls, message: str, branch: str, workflow: dict,
               parent_id: Optional[str] = None) -> "Snapshot":
        return cls(
            id=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            branch=branch,
            workflow=workflow,
            parent_id=parent_id,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "workflow": self.workflow,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(
            id=data["id"],
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            branch=data["branch"],
            workflow=data["workflow"],
            parent_id=data.get("parent_id"),
        )

    @property
    def short_id(self) -> str:
        return self.id[:7]

    @property
    def node_count(self) -> int:
        return len(self.workflow.get("nodes", []))


@dataclass
class Branch:
    name: str
    head: Optional[str] = None
    snapshots: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "head": self.head, "snapshots": self.snapshots}

    @classmethod
    def from_dict(cls, data: dict) -> "Branch":
        return cls(
            name=data["name"],
            head=data.get("head"),
            snapshots=data.get("snapshots", []),
        )
