"""原子写文件辅助。

统一"先写临时文件并 fsync、再 os.replace 覆盖目标"的持久化流程，保证读者永远
看不到半成品，并在任意中断路径上清理临时文件（避免 delete=False 临时文件泄漏）。
Memory 长期记忆与 run artifact 两条持久化路径共用此实现，避免各自维护易漂移的副本。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """以持久、原子的方式把 text 写入 path，返回目标路径。

    同目录创建临时文件 → write → flush → fsync → os.replace 覆盖目标；无论成功或
    失败都在 finally 清理残留临时文件。temporary_path 在写入前即记录，确保写入阶段
    抛异常时临时文件也能被回收。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return target
