# ComfyVC — ComfyUI Workflow Version Control

A desktop app for snapshotting, branching, and diffing ComfyUI workflow files.
Never lose a working workflow again.

[![CI](https://github.com/mkaizen/ComfyUI-Workflow-Version-Control/actions/workflows/ci.yml/badge.svg)](https://github.com/mkaizen/ComfyUI-Workflow-Version-Control/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


![alt text](https://i.imgur.com/8ya6NRi.png)

## Features

- **Snapshots** — save the state of any workflow JSON with a message
- **Branches** — experiment on a branch without touching your working version
- **Diff viewer** — select any two snapshots to see exactly which nodes were added, removed, or changed
- **Restore** — roll back to any previous snapshot in one click
- **Zero lock-in** — snapshots stored as plain JSON in a `.comfyvc/` folder next to your workflow

---

## Installation

```bash
git clone https://github.com/mkaizen/comfyui-workflow-vc
cd comfyui-workflow-vc
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+ and PyQt6.

---

## Usage

1. Click **Open Workflow** and select your ComfyUI `.json` workflow file
2. Click **📸 Take Snapshot** after any meaningful change, give it a message
3. Switch branches with the dropdown — use **+** to create a new one
4. **Ctrl+click** any two snapshots in the list to see a node-level diff
5. Select one snapshot and click **⏪ Restore** to roll back

---

## How It Works

Snapshots and branch metadata are stored in a `.comfyvc/` directory created
alongside your workflow file. Each snapshot is a plain JSON file containing the
full workflow state and metadata (timestamp, message, parent). Nothing is
uploaded anywhere.

```
my_workflow.json
.comfyvc/
  meta.json              # branch pointers
  snapshots/
    <uuid>.json          # one file per snapshot
    <uuid>.json
```

The diff engine compares workflows at the node level — it indexes nodes by their
ComfyUI `id` field and reports added, removed, and field-level modifications
rather than showing a raw text diff.

---

## License

[MIT](LICENSE)
