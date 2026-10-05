"""Disposable, uniquely named fixture directories with inherited Windows ACLs."""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import uuid


@contextmanager
def workspace_directory(prefix):
    root = Path(__file__).resolve().parent
    if prefix not in {"_smoke_test_", "_extract_test_"}:
        raise ValueError("unknown fixture prefix")
    path = root / (prefix + uuid.uuid4().hex)
    # mkdtemp uses mode 0700, which denies the test child processes access in
    # some Windows sandboxes. Fixtures contain synthetic data only.
    os.mkdir(path)
    try:
        yield str(path)
    finally:
        if path.parent.resolve() != root or path.is_symlink():
            raise RuntimeError("unsafe fixture cleanup")
        shutil.rmtree(path)
