import logging

import src.webui_frontend as webui_frontend


def _prepare_fake_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    module_path = repo_root / "src" / "webui_frontend.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    monkeypatch.setattr(webui_frontend, "__file__", str(module_path))
    return repo_root


def _create_full_static(repo_root):
    """Create static/index.html + static/assets/*.js/.css (complete build)."""
    static_dir = repo_root / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (assets_dir / "index-abc123.js").write_text("/* js */", encoding="utf-8")
    (assets_dir / "index-abc123.css").write_text("/* css */", encoding="utf-8")
    return static_dir


def test_prepare_webui_frontend_assets_reuses_prebuilt_static_without_source(tmp_path, monkeypatch, caplog):
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    _create_full_static(repo_root)

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)
    monkeypatch.setattr(webui_frontend.shutil, "which", lambda _: None)

    with caplog.at_level(logging.INFO):
        assert webui_frontend.prepare_webui_frontend_assets() is True

    assert "\u68c0\u6d4b\u5230\u53ef\u76f4\u63a5\u590d\u7528\u7684\u524d\u7aef\u9759\u6001\u4ea7\u7269" in caplog.text
    assert "\u672a\u627e\u5230\u524d\u7aef\u9879\u76ee，\u65e0\u6cd5\u81ea\u52a8\u6784\u5efa" not in caplog.text
    assert "\u672a\u68c0\u6d4b\u5230 npm，\u65e0\u6cd5\u81ea\u52a8\u6784\u5efa\u524d\u7aef" not in caplog.text
    assert "assets/ \u76ee\u5f55\u4e0d\u5b58\u5728\u6216\u65e0 CSS/JS \u6587\u4ef6" not in caplog.text


def test_prepare_webui_frontend_assets_fails_without_static_or_source(tmp_path, monkeypatch, caplog):
    _prepare_fake_repo(tmp_path, monkeypatch)

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)

    with caplog.at_level(logging.WARNING):
        assert webui_frontend.prepare_webui_frontend_assets() is False

    assert "\u672a\u627e\u5230\u524d\u7aef\u9879\u76ee，\u65e0\u6cd5\u81ea\u52a8\u6784\u5efa" in caplog.text


def test_prepare_webui_frontend_assets_warns_when_assets_missing(tmp_path, monkeypatch, caplog):
    """index.html \u5b58\u5728\u4f46 static/assets/ \u7f3a\u5931\u65f6\u5e94\u53d1\u51fa WebUI \u663e\u793a\u5f02\u5e38\u8b66\u544a（Issue #944）。"""
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    static_index = repo_root / "static" / "index.html"
    static_index.parent.mkdir(parents=True)
    static_index.write_text("<!doctype html>", encoding="utf-8")
    # No assets directory created — simulates incomplete/broken build

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)
    monkeypatch.setattr(webui_frontend.shutil, "which", lambda _: None)

    with caplog.at_level(logging.WARNING):
        result = webui_frontend.prepare_webui_frontend_assets()

    assert result is True  # function still returns True (index.html present)
    assert "\u76ee\u5f55\u4e0d\u5b58\u5728\u6216\u65e0 CSS/JS \u6587\u4ef6" in caplog.text
    assert "WebUI \u5c06\u56e0\u7f3a\u5c11\u6837\u5f0f\u4e0e\u811a\u672c\u800c\u663e\u793a\u5f02\u5e38" in caplog.text


def test_prepare_webui_frontend_assets_auto_build_disabled_warns_when_assets_missing(tmp_path, monkeypatch, caplog):
    """WEBUI_AUTO_BUILD=false \u4e14 assets \u7f3a\u5931\u65f6\u4e5f\u5e94\u53d1\u51fa\u8b66\u544a。"""
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    static_index = repo_root / "static" / "index.html"
    static_index.parent.mkdir(parents=True)
    static_index.write_text("<!doctype html>", encoding="utf-8")
    # No assets directory — simulates state where only index.html exists

    monkeypatch.setenv("WEBUI_AUTO_BUILD", "false")
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)

    with caplog.at_level(logging.WARNING):
        result = webui_frontend.prepare_webui_frontend_assets()

    assert result is True  # index.html present, still returns True
    assert "\u76ee\u5f55\u4e0d\u5b58\u5728\u6216\u65e0 CSS/JS \u6587\u4ef6" in caplog.text


def test_has_static_assets_returns_false_for_missing_dir(tmp_path):
    assert webui_frontend._has_static_assets(tmp_path / "nonexistent") is False


def test_has_static_assets_returns_false_for_empty_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    assert webui_frontend._has_static_assets(tmp_path) is False


def test_has_static_assets_returns_true_when_js_present(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("", encoding="utf-8")
    assert webui_frontend._has_static_assets(tmp_path) is True


def test_has_static_assets_returns_true_when_css_present(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "style.css").write_text("", encoding="utf-8")
    assert webui_frontend._has_static_assets(tmp_path) is True
