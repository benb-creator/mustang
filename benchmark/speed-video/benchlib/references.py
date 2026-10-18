from pathlib import Path

import numpy as np
from PIL import Image

from .settle import Rect, Region


class References:
    """Where the calibration run's reference images live, for the analysis and the live gate alike.

    Full-frame reference of a step: references/<app>/<task>/<step>.png (or the step's `expect` path).
    Region references: <step>@<region>.png (completion check), <step>.first@<region>.png ("first messages
    visible"), <step>.verify@<region>.png (state after the verify actions)."""

    kinds = {"end": "", "first": ".first", "verify": ".verify"}

    def __init__(self, workdir: Path):
        self.root = Path(workdir) / "references"

    def step(self, app_id: str, task_id: str, step_name: str) -> Path:
        return self.root / app_id / task_id / f"{step_name}.png"

    def full_frame(self, app_id: str, task_id: str, step) -> Path | None:
        if not step.expect or str(step.expect).lower() == "none":
            return None
        if step.expect == "auto":
            return self.step(app_id, task_id, step.name)
        return self.root / str(step.expect)

    def region(self, app_id: str, task_id: str, step_name: str, kind: str, region: str) -> Path:
        return self.root / app_id / task_id / f"{step_name}{self.kinds[kind]}@{region}.png"

    def opening(self, app_id: str, task_id: str, region: str) -> Path:
        return self.root / app_id / task_id / f"opening@{region}.png"

    def checks(self, step, kind: str) -> list:
        if kind == "end":
            return list(step.regions)
        if kind == "first":
            return [step.first_visible] if step.first_visible else []
        return list(step.verify.regions) if step.verify else []

    def regions(self, app_id: str, task_id: str, step, kind: str, rects: dict[str, Rect],
                load: bool = True) -> list[Region]:
        out = []
        for check in self.checks(step, kind):
            if check.region not in rects:
                raise KeyError(f"Region '{check.region}' of step '{step.name}' is not calibrated "
                               f"(bench.py calibrate points --app {app_id})")
            path = self.region(app_id, task_id, step.name, kind, check.region)
            reference = np.asarray(Image.open(path).convert("RGB")) if load and path.exists() else None
            out.append(Region(check.region, rects[check.region], reference, check.tolerance, check.pixel_threshold))
        return out
