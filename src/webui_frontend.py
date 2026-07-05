# -*- coding: utf-8 -*-
"""
WebUI frontend asset preparation helper.

Default behavior runs startup-time frontend auto build.
Set WEBUI_AUTO_BUILD=false to disable auto build and only verify artifacts.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

_FALSEY_ENV_VALUES = {"0", "false", "no", "off"}
_BUILD_INPUT_FILES = (
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "eslint.config.js",
    "postcss.config.js",
    "tailwind.config.js",
    "index.html",
)
_BUILD_INPUT_DIRS = ("src", "public")


def _is_truthy_env(var_name: str, default: str = "true") -> bool:
    """\u89e3\u6790\u5e38\u89c1\u7684\u73af\u5883\u53d8\u91cf\u771f\u503c/\u5047\u503c\u8868\u8fbe (\u5927\u5c0f\u5199\u4e0d\u654f\u611f)."""
    value = os.getenv(var_name, default).strip().lower()
    return value not in _FALSEY_ENV_VALUES


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _tree_latest_mtime(root: Path) -> float:
    if not root.exists():
        return 0.0
    latest = 0.0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                latest = max(latest, _safe_mtime(p))
    except OSError:
        # Fallback to root mtime when recursive traversal fails on restricted envs.
        latest = max(latest, _safe_mtime(root))
    return latest


def _max_mtime(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        latest = max(latest, _safe_mtime(path))
    return latest


def _resolve_artifact_index(frontend_dir: Path) -> Path:
    # Prefer static/index.html because it is the configured output path in this repo.
    static_index = (frontend_dir / ".." / ".." / "static" / "index.html").resolve()
    dist_index = frontend_dir / "dist" / "index.html"
    build_index = frontend_dir / "build" / "index.html"
    if static_index.exists():
        return static_index

    fallback_candidates = [p for p in (dist_index, build_index) if p.exists()]
    if not fallback_candidates:
        return static_index
    return max(fallback_candidates, key=_safe_mtime)


def _needs_dependency_install(frontend_dir: Path, package_json: Path, lock_file: Path, force_build: bool) -> bool:
    node_modules_dir = frontend_dir / "node_modules"
    install_marker = node_modules_dir / ".package-lock.json"
    deps_marker_mtime = _safe_mtime(install_marker) if install_marker.exists() else _safe_mtime(node_modules_dir)
    deps_input_mtime = _max_mtime((package_json, lock_file))
    return force_build or (not node_modules_dir.exists()) or (deps_marker_mtime < deps_input_mtime)


def _collect_build_inputs_latest_mtime(frontend_dir: Path) -> float:
    latest = _max_mtime(frontend_dir / filename for filename in _BUILD_INPUT_FILES)
    for dirname in _BUILD_INPUT_DIRS:
        latest = max(latest, _tree_latest_mtime(frontend_dir / dirname))
    return latest


def _needs_frontend_build(frontend_dir: Path, force_build: bool) -> tuple[bool, Path]:
    artifact_index = _resolve_artifact_index(frontend_dir)
    inputs_latest_mtime = _collect_build_inputs_latest_mtime(frontend_dir)
    artifact_mtime = _safe_mtime(artifact_index)
    needs_build = force_build or (not artifact_index.exists()) or (artifact_mtime < inputs_latest_mtime)
    return needs_build, artifact_index


def _run_frontend_commands(commands: Sequence[Sequence[str]], frontend_dir: Path) -> bool:
    try:
        for command in commands:
            logger.info("\u6267\u884c\u524d\u7aefcommand: %s", " ".join(command))
            subprocess.run(command, cwd=frontend_dir, check=True)
        logger.info("\u524d\u7aef\u9759\u6001\u8d44\u6e90\u6784\u5efa\u5b8c\u6210")
        return True
    except subprocess.CalledProcessError as exc:
        cmd_display = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        logger.error(
            "\u524d\u7aefcommand execution failed (exit_code=%s): %s",
            getattr(exc, "returncode", "N/A"),
            cmd_display,
        )
        return False


def _manual_build_command(frontend_dir: Path) -> str:
    lock_file = frontend_dir / "package-lock.json"
    install_cmd = "npm ci" if lock_file.exists() else "npm install"
    return f'cd "{frontend_dir}" && {install_cmd} && npm run build'


def _has_static_assets(static_dir: Path) -> bool:
    """\u68c0check static/assets/ \u662f\u5426\u5b58\u5728\u4e14\u5305\u542b CSS/JS \u6587\u4ef6.

    index.html \u5b58\u5728\u4f46 assets/ \u4e3a\u7a7aor\u7f3a\u5931\u65f6; \u6d4f\u89c8\u5668\u65e0\u6cd5load\u6837\u5f0f\u4e0e\u811a\u672c;
    \u4f1a\u5bfc\u81f4\u9875\u9762\u5143\u7d20\u5f02\u5e38\u653e\u5927、\u5e03\u5c40\u9519\u4e71 (\u7eaf\u88f8 HTML \u6e32\u67d3).
    """
    assets_dir = static_dir / "assets"
    if not assets_dir.is_dir():
        return False
    try:
        return any(
            f.suffix in (".js", ".css") and f.is_file()
            for f in assets_dir.iterdir()
        )
    except OSError:
        return False


def _warn_if_assets_missing(artifact_index: Path, frontend_dir: Path) -> None:
    """\u5f53 index.html \u5b58\u5728\u4f46 assets/ \u7f3a\u5931\u65f6; \u53d1\u51fa\u9875\u9762\u663e\u793a\u5f02\u5e38warning."""
    static_dir = artifact_index.parent
    assets_dir = static_dir / "assets"
    if not _has_static_assets(static_dir):
        logger.warning(
            "\u68c0\u6d4b\u5230 %s \u4f46 %s \u76ee\u5f55does not existor\u65e0 CSS/JS \u6587\u4ef6; "
            "WebUI \u5c06\u56e0\u7f3a\u5c11\u6837\u5f0f\u4e0e\u811a\u672c\u800c\u663e\u793a\u5f02\u5e38 (\u5143\u7d20\u8fc7\u5927、\u5e03\u5c40\u9519\u4e71)",
            artifact_index,
            assets_dir,
        )
        logger.warning(
            "\u8bf7\u91cd\u65b0\u6784\u5efa\u524d\u7aef\u4ee5\u4fee\u590d\u6b64question: %s",
            _manual_build_command(frontend_dir),
        )
        logger.warning(
            "Docker user\u8bf7\u6267\u884c: docker-compose -f ./docker/docker-compose.yml build --no-cache"
        )


def prepare_webui_frontend_assets() -> bool:
    """
    Prepare frontend assets for WebUI startup.

    Default mode (WEBUI_AUTO_BUILD=true):
    - Run npm install/build when dependencies or sources changed,
      or artifacts are missing.

    Manual mode (WEBUI_AUTO_BUILD=false):
    - Do not compile frontend during backend startup.
    - Only check whether existing artifacts are available.
    """
    frontend_dir = Path(__file__).resolve().parent.parent / "apps" / "dsa-web"
    auto_build_enabled = _is_truthy_env("WEBUI_AUTO_BUILD", "true")
    artifact_index = _resolve_artifact_index(frontend_dir)

    if not auto_build_enabled:
        if artifact_index.exists():
            logger.info("WEBUI_AUTO_BUILD=false; \u68c0\u6d4b\u5230\u524d\u7aef\u9759\u6001\u4ea7\u7269: %s", artifact_index)
            _warn_if_assets_missing(artifact_index, frontend_dir)
            return True
        logger.warning("\u672a\u68c0\u6d4b\u5230 WebUI \u524d\u7aef\u9759\u6001\u4ea7\u7269: %s", artifact_index)
        logger.warning("\u5f53\u524dconfig WEBUI_AUTO_BUILD=false; \u4e0d\u4f1a\u5728\u540e\u7aefstarted\u65f6\u81ea\u52a8\u7f16\u8bd1\u524d\u7aef")
        logger.warning("\u8bf7\u5148\u624b\u52a8\u6784\u5efa\u524d\u7aef: %s", _manual_build_command(frontend_dir))
        logger.warning("\u5982\u9700started\u65f6\u81ea\u52a8\u6784\u5efa; \u53ef\u8bbe\u7f6e WEBUI_AUTO_BUILD=true")
        return False

    force_build = _is_truthy_env("WEBUI_FORCE_BUILD", "false")
    needs_build, artifact_index = _needs_frontend_build(frontend_dir=frontend_dir, force_build=force_build)

    if not needs_build:
        logger.info("\u68c0\u6d4b\u5230\u53ef\u76f4\u63a5\u590d\u7528\u7684\u524d\u7aef\u9759\u6001\u4ea7\u7269; skipping\u8fd0\u884c\u65f6\u81ea\u52a8\u6784\u5efa: %s", artifact_index)
        _warn_if_assets_missing(artifact_index, frontend_dir)
        return True

    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        logger.warning("\u672a\u627e\u5230\u524d\u7aef\u9879\u76ee; \u65e0\u6cd5\u81ea\u52a8\u6784\u5efa: %s", package_json)
        logger.warning("\u53ef\u5148\u624b\u52a8\u68c0check\u524d\u7aef\u76ee\u5f55or\u5173\u95ed WEBUI_AUTO_BUILD")
        return False

    npm_path = shutil.which("npm")
    if not npm_path:
        logger.warning("\u672a\u68c0\u6d4b\u5230 npm; \u65e0\u6cd5\u81ea\u52a8\u6784\u5efa\u524d\u7aef")
        logger.warning("\u8bf7\u5148\u624b\u52a8\u6784\u5efa\u524d\u7aef\u9759\u6001\u8d44\u6e90: %s", _manual_build_command(frontend_dir))
        return False

    lock_file = frontend_dir / "package-lock.json"
    needs_install = _needs_dependency_install(
        frontend_dir=frontend_dir,
        package_json=package_json,
        lock_file=lock_file,
        force_build=force_build,
    )

    commands = []
    if needs_install:
        lock_exists = (frontend_dir / "package-lock.json").exists()
        commands.append([npm_path, "ci" if lock_exists else "install"])
    if needs_build:
        commands.append([npm_path, "run", "build"])

    logger.info(
        "\u524d\u7aef\u6784\u5efa\u68c0checkresult: needs_install=%s, needs_build=%s, artifact=%s",
        needs_install,
        needs_build,
        artifact_index,
    )
    return _run_frontend_commands(commands=commands, frontend_dir=frontend_dir)
