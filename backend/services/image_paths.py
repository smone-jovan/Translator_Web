"""Per-workspace on-disk locations for thread images (uploads/images)."""
import shutil
from pathlib import Path

from database import normalize_workspace

IMAGES_ROOT = Path("uploads") / "images"


def thread_image_subdir(workspace, thread_id: int) -> str:
    """Relative folder for a thread's images. `main` keeps the legacy layout so stored URLs
    stay valid; `ghost` gets its own namespace because thread ids are per-DB and collide."""
    name = f"thread_{int(thread_id)}"
    return name if normalize_workspace(workspace) == "main" else f"{normalize_workspace(workspace)}/{name}"


def delete_thread_images(workspace, thread_id: int, images_root: Path = IMAGES_ROOT) -> bool:
    """Remove a thread's image folder. Returns True when a folder was deleted."""
    base = Path(images_root).resolve()
    target = (base / thread_image_subdir(workspace, thread_id)).resolve()
    if target == base or not target.is_relative_to(base) or not target.is_dir():
        return False
    shutil.rmtree(target, ignore_errors=True)
    return True
