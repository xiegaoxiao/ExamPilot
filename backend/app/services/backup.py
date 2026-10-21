"""Consistent local cold backup; manifest validation before any restore writes."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def create_backup(workspace, output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("备份目标已存在，拒绝覆盖")
    if not output.parent.exists():
        output.parent.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="exampilot-backup-") as temporary:
        stage = Path(temporary)
        (stage / "data").mkdir()
        # The service holds BEGIN IMMEDIATE: no API/CLI business writes can interleave with this snapshot.
        with workspace.service("user") as svc:
            src = sqlite3.connect(workspace.root / "data/exampilot.sqlite3")
            dst = sqlite3.connect(stage / "data/exampilot.sqlite3")
            try:
                src.backup(dst)
            finally:
                src.close()
                dst.close()
            source_dir = workspace.root / "workspace"
            if source_dir.exists():
                for file in source_dir.rglob("*"):
                    if file.is_symlink():
                        raise ValueError("工作区含符号链接，请先审查后再备份")
                shutil.copytree(source_dir, stage / "workspace")
            manifest = {"app_version": "0.1.0", "schema_version": 1, "files": {}}
            for file in stage.rglob("*"):
                if file.is_file():
                    manifest["files"][file.relative_to(stage).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
            with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
                for name in manifest["files"]:
                    archive.write(stage / name, name)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            svc.audit(None, str(output), "backup", files=len(manifest["files"]))
    return {"path": str(output), "files": len(manifest["files"]), "app_version": "0.1.0"}


def restore_backup(archive_path, destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("只允许恢复到空目录；不会覆盖现有工作区")
    with ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("app_version") != "0.1.0" or manifest.get("schema_version") != 1:
            raise ValueError("备份应用/结构版本不兼容，Demo 仅支持同版本恢复")
        names = [n for n in archive.namelist() if n != "manifest.json"]
        if len(names) != len(set(names)) or set(names) != set(manifest["files"]):
            raise ValueError("备份目录与内容清单不一致")
        for name in names:
            resolved = (destination / name).resolve()
            if not resolved.is_relative_to(destination) or not name.startswith(("data/", "workspace/")):
                raise ValueError("备份内含非法路径")
            if hashlib.sha256(archive.read(name)).hexdigest() != manifest["files"][name]:
                raise ValueError("备份内容摘要不一致")
        # Validate all contents and references in a staging directory first; a failed restore leaves destination untouched.
        with tempfile.TemporaryDirectory(prefix="exampilot-restore-") as temporary:
            stage = Path(temporary)
            for name in names:
                file = stage / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(archive.read(name))
            connection = sqlite3.connect(stage / "data/exampilot.sqlite3")
            try:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("备份数据库完整性校验失败")
                sources = connection.execute("SELECT path, sha256 FROM sources").fetchall()
                for path, sha in sources:
                    file = (stage / path).resolve()
                    if not file.is_relative_to(stage) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                        raise ValueError("来源文件缺失或摘要错误")
            finally:
                connection.close()
            destination.mkdir(parents=True, exist_ok=True)
            for child in stage.iterdir():
                shutil.copytree(child, destination / child.name)
    return {"path": str(destination), "status": "restored"}
