"""Issue #26 A-17 / A-23: per-workspace thread image folders and cleanup on delete."""
from services.image_paths import delete_thread_images, thread_image_subdir


def test_main_keeps_legacy_folder_and_ghost_is_separate():
    assert thread_image_subdir("main", 5) == "thread_5"
    assert thread_image_subdir("ghost", 5) == "ghost/thread_5"
    assert thread_image_subdir(None, 5) == thread_image_subdir("main", 5)


def test_delete_thread_images_only_removes_own_workspace_folder(tmp_path):
    main_dir = tmp_path / "thread_5"
    ghost_dir = tmp_path / "ghost" / "thread_5"
    for d in (main_dir, ghost_dir):
        d.mkdir(parents=True)
        (d / "a.png").write_bytes(b"x")

    assert delete_thread_images("ghost", 5, images_root=tmp_path) is True

    assert not ghost_dir.exists()
    assert (main_dir / "a.png").exists()


def test_delete_thread_images_missing_folder_is_noop(tmp_path):
    assert delete_thread_images("main", 99, images_root=tmp_path) is False


def test_delete_thread_endpoint_removes_image_folder(db_session, tmp_path, monkeypatch):
    from database import Thread
    from routers import threads
    from services import image_paths

    monkeypatch.setattr(image_paths, "IMAGES_ROOT", tmp_path)
    monkeypatch.setattr(
        threads, "delete_thread_images",
        lambda ws, tid: image_paths.delete_thread_images(ws, tid, images_root=tmp_path),
    )
    thread = Thread(title="T")
    db_session.add(thread)
    db_session.commit()
    folder = tmp_path / f"thread_{thread.id}"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"x")

    threads.delete_thread(thread.id, db_session)

    assert not folder.exists()
