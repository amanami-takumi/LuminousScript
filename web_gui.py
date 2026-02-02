#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple GUI server for LuminousScript (port 3000)."""

import io
import json
import logging
import mimetypes
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from email.parser import BytesParser
from email.policy import default

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_ROOT / "input"
ASSETS_DIR = INPUT_DIR / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "gui.log"

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LuminousScript GUI</title>
  <style>
    :root {
      --bg: #0C0A09;
      --panel: #171717;
      --panel-2: #10151e;
      --text: #e6e9ef;
      --muted: #98a2b3;
      --accent: #0F172B;
      --accent-2: #0F172B;
      --danger: #ff6b6b;
      --border: #232a3a;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Noto Sans JP", "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif;
      background: radial-gradient(1200px 600px at 20% -10%, #1d2434 0%, transparent 60%),
                  radial-gradient(900px 500px at 120% 10%, #1a1f30 0%, transparent 55%),
                  var(--bg);
      color: var(--text);
    }

    header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(90deg, #0C0A09, #0f1116);
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    h1 {
      margin: 0 0 6px 0;
      font-size: 20px;
      letter-spacing: 0.5px;
    }

    .subtitle {
      color: var(--muted);
      font-size: 12px;
    }

    .container {
      padding: 18px 24px 36px;
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(2, minmax(280px, 1fr));
      grid-template-areas:
        "assets input"
        "build output"
        "logs logs";
    }

    .card {
      background: linear-gradient(180deg, var(--panel));
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      min-height: 220px;
    }

    .card h2 {
      font-size: 14px;
      margin: 0 0 10px 0;
      letter-spacing: 0.4px;
    }

    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .row + .row { margin-top: 8px; }

    input[type="text"], input[type="file"], select, textarea {
      background: #0C0A09;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 12px;
    }

    textarea { width: 100%; height: 180px; resize: vertical; }

    button {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #fff;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 12px;
      cursor: pointer;
    }

    button.secondary {
      background: #1b2231;
      color: var(--text);
      border: 1px solid var(--border);
    }

    button.danger {
      background: #2a1517;
      border: 1px solid #3f1f21;
      color: var(--danger);
    }

    .list {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px;
      max-height: 200px;
      overflow: auto;
      background: #0C0A09;
    }

    .list-item {
      padding: 6px 8px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      cursor: pointer;
    }

    .list-item:hover { background: #141c2a; }
    .list-item.active { background: #1e2637; }

    .muted { color: var(--muted); font-size: 11px; }

    .preview {
      border: 1px dashed var(--border);
      border-radius: 8px;
      padding: 8px;
      min-height: 160px;
      background: #0C0A09;
      font-size: 11px;
      color: var(--muted);
    }

    .preview-grid {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    }

    .preview-tile {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px;
      background: #0e1421;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 6px;
      cursor: pointer;
      text-align: center;
    }

    .preview-tile:hover { background: #141c2a; }
    .preview-tile.active { outline: 2px solid var(--accent); }

    .preview-tile img, .preview-tile audio {
      max-width: 100%;
      max-height: 70px;
    }

    .preview-name {
      font-size: 10px;
      color: var(--muted);
      word-break: break-all;
    }

    .status {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }

    .badge {
      padding: 2px 6px;
      border-radius: 6px;
      background: #1b2231;
      font-size: 10px;
      color: var(--muted);
    }

    .path {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
      word-break: break-all;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .header-actions button {
      padding: 6px 10px;
      font-size: 11px;
    }

    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(10, 12, 18, 0.88);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .overlay-card {
      background: linear-gradient(180deg, var(--panel));
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      width: min(360px, 90vw);
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
    }

    .overlay-card h2 {
      margin: 0 0 8px 0;
      font-size: 14px;
    }

    .overlay-card input {
      width: 100%;
      margin: 8px 0 12px 0;
    }

    .assets-card { grid-area: assets; }
    .input-card { grid-area: input; }
    .build-card { grid-area: build; }
    .output-card { grid-area: output; }
    .logs-card { grid-area: logs; }

    @media (max-width: 860px) {
      .container {
        grid-template-columns: 1fr;
        grid-template-areas:
          "assets"
          "input"
          "build"
          "output"
          "logs";
      }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>LuminousScript GUI (Port 3000)</h1>
      <div class="subtitle">assets / CSV / config / output / build / logs</div>
    </div>
    <div class="header-actions">
      <button class="secondary" onclick="resetPassword()">パスワード変更</button>
    </div>
  </header>

  <div class="overlay" id="passwordOverlay">
    <div class="overlay-card">
      <h2>パスワードを入力</h2>
      <div class="muted">最初に一度入力すると自動入力されます。</div>
      <input type="password" id="passwordInput" placeholder="password" />
      <button onclick="submitPassword()">入室</button>
    </div>
  </div>

  <div class="container">
    <section class="card assets-card">
      <h2>Assets 管理</h2>
      <div class="path" id="assetsPath"></div>
      <div class="list" id="assetsList"></div>
      <div class="row">
        <input type="file" id="assetsUpload" multiple style="display:none" />
        <button onclick="openAssetsPicker()">アップロード</button>
        <button class="secondary" onclick="downloadSelectedAsset()">ダウンロード</button>
        <button class="danger" onclick="deleteSelectedAsset()">削除</button>
      </div>
      <div class="row">
        <input type="text" id="renameFrom" placeholder="old/path.png" />
        <input type="text" id="renameTo" placeholder="new/path.png" />
        <button class="secondary" onclick="renameAsset()">名前変更</button>
      </div>
      <div class="preview" id="assetsPreview"></div>
    </section>

    <section class="card input-card">
      <h2>CSV / config.yml</h2>
      <div class="list" id="inputList"></div>
      <div class="row">
        <span class="badge" id="inputSelectedName">未選択</span>
        <button class="secondary" onclick="downloadSelectedInput()">ダウンロード</button>
        <button onclick="saveInputText()">保存</button>
      </div>
      <div class="row">
        <input type="file" id="csvUpload" accept=".csv" style="display:none" />
        <button onclick="openCsvPicker()">CSVアップロード</button>
      </div>
      <div class="row">
        <input type="file" id="configUpload" accept=".yml,.yaml" style="display:none" />
        <button onclick="openConfigPicker()">config.ymlアップロード</button>
      </div>
      <textarea id="inputEditor" placeholder="CSV / config.yml を編集"></textarea>
    </section>

    <section class="card output-card">
      <h2>Output</h2>
      <div class="path" id="outputPath"></div>
      <div class="list" id="outputList"></div>
      <div class="row">
        <button class="secondary" onclick="refreshOutput()">更新</button>
      </div>
    </section>

    <section class="card build-card">
      <h2>Build</h2>
      <div class="row">
        <select id="buildCsv"></select>
        <button onclick="buildGame()">ゲームをビルド</button>
      </div>
      <div class="status" id="buildStatus">待機中</div>
    </section>

    <section class="card logs-card">
      <h2>ログ</h2>
      <div class="row">
        <button class="secondary" onclick="refreshLogs()">ログ更新</button>
      </div>
      <textarea id="logViewer" readonly></textarea>
    </section>
  </div>

  <script>
    const state = {
      assetsDir: "",
      outputDir: "",
      assetsSelected: null,
      inputSelected: null,
    };

    const PASSWORD = "luminous";
    const PASSWORD_KEY = "luminous_gui_password";

    function setStatus(message) {
      const el = document.getElementById("buildStatus");
      if (el) el.textContent = message;
    }

    async function apiGet(path, params = {}) {
      const url = new URL(path, window.location.origin);
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
      const res = await fetch(url);
      if (!res.ok) throw new Error(await res.text());
      return res.headers.get("content-type")?.includes("application/json") ? res.json() : res.text();
    }

    async function apiPost(path, body, isJson = true) {
      const res = await fetch(path, {
        method: "POST",
        headers: isJson ? { "Content-Type": "application/json" } : undefined,
        body: isJson ? JSON.stringify(body) : body,
      });
      if (!res.ok) throw new Error(await res.text());
      return res.headers.get("content-type")?.includes("application/json") ? res.json() : res.text();
    }

    function renderList(el, entries, onClick, options = {}) {
      const { includeParent = false, currentDir = "" } = options;
      el.innerHTML = "";
      if (includeParent && currentDir) {
        const parent = document.createElement("div");
        parent.className = "list-item";
        parent.innerHTML = `<span>📁 ..</span><span class="badge">dir</span>`;
        parent.onclick = () => onClick({ type: "dir", rel_path: parentPath(currentDir), name: ".." });
        el.appendChild(parent);
      }
      if (!entries.length) {
        const empty = document.createElement("div");
        empty.className = "muted";
        empty.textContent = "空";
        el.appendChild(empty);
        return;
      }
      entries.forEach((entry) => {
        const row = document.createElement("div");
        row.className = "list-item";
        row.innerHTML = `<span>${entry.type === "dir" ? "📁" : "📄"} ${entry.name}</span><span class="badge">${entry.type}</span>`;
        row.onclick = () => onClick(entry);
        el.appendChild(row);
      });
    }

    function parentPath(path) {
      const parts = path.split("/").filter(Boolean);
      parts.pop();
      return parts.join("/");
    }

    async function refreshAssets() {
      const data = await apiGet("/api/assets/list", { dir: state.assetsDir });
      document.getElementById("assetsPath").textContent = `input/assets/${data.dir || ""}`;
      renderList(document.getElementById("assetsList"), data.entries, (entry) => {
        if (entry.type === "dir") {
          state.assetsDir = entry.rel_path;
          refreshAssets();
        } else {
          state.assetsSelected = entry;
          selectAsset(entry);
        }
      }, { includeParent: true, currentDir: data.dir });
      renderAssetsPreview(data.entries);
    }

    function renderAssetsPreview(entries) {
      const preview = document.getElementById("assetsPreview");
      preview.innerHTML = "";
      const files = entries.filter((entry) => entry.type === "file");
      if (!files.length) {
        preview.textContent = "この階層にはファイルがありません";
        return;
      }
      const grid = document.createElement("div");
      grid.className = "preview-grid";
      files.forEach((entry) => {
        const tile = document.createElement("div");
        tile.className = "preview-tile";
        tile.onclick = () => selectAsset(entry);
        const url = `/api/download?base=assets&path=${encodeURIComponent(entry.rel_path)}&inline=1`;
        const ext = entry.name.split(".").pop().toLowerCase();
        if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
          tile.innerHTML = `<img src="${url}" alt="${entry.name}" /><div class="preview-name">${entry.name}</div>`;
        } else if (["mp3", "wav", "ogg"].includes(ext)) {
          tile.innerHTML = `<audio controls src="${url}"></audio><div class="preview-name">${entry.name}</div>`;
        } else {
          tile.innerHTML = `<div>📄</div><div class="preview-name">${entry.name}</div>`;
        }
        grid.appendChild(tile);
      });
      preview.appendChild(grid);
    }

    function selectAsset(entry) {
      state.assetsSelected = entry;
      const renameFrom = document.getElementById("renameFrom");
      renameFrom.value = entry.rel_path;
      const tiles = document.querySelectorAll(".preview-tile");
      tiles.forEach((tile) => tile.classList.remove("active"));
      const matching = Array.from(tiles).find((tile) => {
        const name = tile.querySelector(".preview-name");
        return name && name.textContent === entry.name;
      });
      if (matching) matching.classList.add("active");
    }

    async function downloadSelectedAsset() {
      if (!state.assetsSelected) return alert("ファイルを選択してください");
      window.open(`/api/download?base=assets&path=${encodeURIComponent(state.assetsSelected.rel_path)}`, "_blank");
    }

    async function deleteSelectedAsset() {
      if (!state.assetsSelected) return alert("ファイルを選択してください");
      if (!confirm(`削除しますか？\\n${state.assetsSelected.rel_path}`)) return;
      await apiPost("/api/delete/assets", { path: state.assetsSelected.rel_path });
      state.assetsSelected = null;
      document.getElementById("renameFrom").value = "";
      refreshAssets();
    }

    function openAssetsPicker() {
      const input = document.getElementById("assetsUpload");
      input.click();
    }

    async function uploadAssets() {
      const input = document.getElementById("assetsUpload");
      if (!input.files.length) return;
      const form = new FormData();
      Array.from(input.files).forEach((file) => form.append("file", file));
      form.append("dir", state.assetsDir);
      await apiPost("/api/upload/assets", form, false);
      input.value = "";
      refreshAssets();
    }

    async function renameAsset() {
      const oldPath = document.getElementById("renameFrom").value.trim();
      const newPath = document.getElementById("renameTo").value.trim();
      if (!oldPath || !newPath) return alert("旧/新パスを入力してください");
      await apiPost("/api/rename/assets", { old: oldPath, new: newPath });
      document.getElementById("renameFrom").value = "";
      document.getElementById("renameTo").value = "";
      refreshAssets();
    }

    async function refreshInput() {
      const data = await apiGet("/api/input/list");
      const list = document.getElementById("inputList");
      renderList(list, data.entries, (entry) => {
        if (entry.type === "file") {
          selectInput(entry);
        }
      });
      const select = document.getElementById("buildCsv");
      select.innerHTML = "";
      data.entries
        .filter((entry) => entry.name.endsWith(".csv"))
        .forEach((entry) => {
          const option = document.createElement("option");
          option.value = entry.name;
          option.textContent = entry.name;
          select.appendChild(option);
        });
    }

    function selectInput(entry) {
      state.inputSelected = entry;
      document.getElementById("inputSelectedName").textContent = entry.name;
      if (entry.name === "config.yml" || entry.name.endsWith(".csv")) {
        loadInputText(entry.name);
      }
    }

    async function loadInputText(filename) {
      const content = await apiGet("/api/text", { base: "input", path: filename });
      document.getElementById("inputEditor").value = content;
    }

    function openCsvPicker() {
      const input = document.getElementById("csvUpload");
      input.click();
    }

    async function uploadCsv() {
      const input = document.getElementById("csvUpload");
      if (!input.files.length) return;
      const form = new FormData();
      form.append("file", input.files[0]);
      await apiPost("/api/upload/input", form, false);
      input.value = "";
      refreshInput();
    }

    function openConfigPicker() {
      const input = document.getElementById("configUpload");
      input.click();
    }

    async function uploadConfig() {
      const input = document.getElementById("configUpload");
      if (!input.files.length) return;
      const form = new FormData();
      form.append("file", input.files[0]);
      await apiPost("/api/upload/input?force=config.yml", form, false);
      input.value = "";
      refreshInput();
    }

    async function downloadSelectedInput() {
      if (!state.inputSelected) return alert("ファイルを選択してください");
      window.open(`/api/download?base=input&path=${encodeURIComponent(state.inputSelected.rel_path)}`, "_blank");
    }

    async function saveInputText() {
      if (!state.inputSelected) return alert("ファイルを選択してください");
      const filename = state.inputSelected.name;
      const content = document.getElementById("inputEditor").value;
      await apiPost("/api/text", { base: "input", path: filename, content });
      refreshInput();
    }

    async function refreshOutput() {
      const data = await apiGet("/api/output/list", { dir: state.outputDir });
      document.getElementById("outputPath").textContent = `output/${data.dir || ""}`;
      renderList(document.getElementById("outputList"), data.entries, (entry) => {
        if (entry.type === "dir") {
          state.outputDir = entry.rel_path;
          refreshOutput();
        } else {
          window.open(`/api/download?base=output&path=${encodeURIComponent(entry.rel_path)}`, "_blank");
        }
      });
    }

    async function buildGame() {
      const csv = document.getElementById("buildCsv").value;
      if (!csv) return alert("CSVを選択してください");
      setStatus("ビルド中...");
      try {
        const result = await apiPost("/api/build", { csv });
        setStatus(result.message || "完了");
        refreshOutput();
        refreshLogs();
      } catch (err) {
        setStatus(`失敗: ${err.message}`);
      }
    }

    async function refreshLogs() {
      const text = await apiGet("/api/logs", { lines: 200 });
      document.getElementById("logViewer").value = text;
    }

    async function ensurePassword() {
      const stored = localStorage.getItem(PASSWORD_KEY) || "";
      if (stored === PASSWORD) {
        unlockUI();
        return;
      }
      document.getElementById("passwordOverlay").style.display = "flex";
      document.getElementById("passwordInput").value = stored;
      document.getElementById("passwordInput").focus();
    }

    function unlockUI() {
      document.getElementById("passwordOverlay").style.display = "none";
      refreshAssets();
      refreshInput();
      refreshOutput();
      refreshLogs();
    }

    function submitPassword() {
      const input = document.getElementById("passwordInput").value;
      if (input !== PASSWORD) {
        alert("パスワードが違います");
        return;
      }
      localStorage.setItem(PASSWORD_KEY, input);
      unlockUI();
    }

    function resetPassword() {
      localStorage.removeItem(PASSWORD_KEY);
      document.getElementById("passwordOverlay").style.display = "flex";
      document.getElementById("passwordInput").value = "";
      document.getElementById("passwordInput").focus();
    }

    async function init() {
      document.getElementById("assetsUpload").addEventListener("change", uploadAssets);
      document.getElementById("csvUpload").addEventListener("change", uploadCsv);
      document.getElementById("configUpload").addEventListener("change", uploadConfig);
      await ensurePassword();
    }

    init().catch((err) => alert(err.message));
  </script>
</body>
</html>
"""


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_path(base: Path, rel: str) -> Path:
    rel = rel.lstrip("/")
    target = (base / rel).resolve()
    base_resolved = base.resolve()
    if str(target) == str(base_resolved):
        return target
    if not str(target).startswith(str(base_resolved) + os.sep):
        raise ValueError("Invalid path")
    return target


def list_dir(base: Path, rel: str) -> dict:
    target = safe_path(base, rel)
    if not target.exists():
        return {"dir": rel, "entries": []}
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        entries.append({
            "name": child.name,
            "rel_path": str((Path(rel) / child.name).as_posix()) if rel else child.name,
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size,
            "mtime": int(child.stat().st_mtime),
        })
    return {"dir": rel, "entries": entries}


def tail_lines(path: Path, lines: int = 200) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        size = 0
        block = 1024
        data = b""
        while end > 0 and data.count(b"\n") <= lines:
            read_size = min(block, end)
            end -= read_size
            f.seek(end)
            chunk = f.read(read_size)
            data = chunk + data
            size += read_size
            if size > 1024 * 1024:
                break
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def read_text_flexible(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "cp932", "shift_jis", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class GUIHandler(BaseHTTPRequestHandler):
    def _parse_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return {}, {}
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}, {}

        body = self.rfile.read(length)
        header = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
        ).encode("utf-8")
        msg = BytesParser(policy=default).parsebytes(header + body)

        fields = {}
        files = {}
        if not msg.is_multipart():
            return fields, files

        for part in msg.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files.setdefault(name, []).append({"filename": filename, "data": payload})
            else:
                charset = part.get_content_charset() or "utf-8"
                value = payload.decode(charset, errors="replace")
                fields.setdefault(name, []).append(value)
        return fields, files

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, inline: bool = False):
        if not path.exists() or not path.is_file():
            self._send_text("Not Found", status=404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"
        with path.open("rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f"{disposition}; filename=\"{path.name}\"")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _parse_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_text(INDEX_HTML, content_type="text/html; charset=utf-8")
                return

            if parsed.path == "/api/assets/list":
                params = parse_qs(parsed.query)
                rel = params.get("dir", [""])[0]
                self._send_json(list_dir(ASSETS_DIR, rel))
                return

            if parsed.path == "/api/output/list":
                params = parse_qs(parsed.query)
                rel = params.get("dir", [""])[0]
                self._send_json(list_dir(OUTPUT_DIR, rel))
                return

            if parsed.path == "/api/input/list":
                data = list_dir(INPUT_DIR, "")
                data["entries"] = [
                    entry for entry in data["entries"]
                    if entry["name"].endswith(".csv") or entry["name"] == "config.yml"
                ]
                self._send_json(data)
                return

            if parsed.path == "/api/text":
                params = parse_qs(parsed.query)
                base = params.get("base", [""])[0]
                rel = params.get("path", [""])[0]
                if base != "input" or (rel != "config.yml" and not rel.endswith(".csv")):
                    self._send_text("Forbidden", status=403)
                    return
                path = safe_path(INPUT_DIR, rel)
                content = read_text_flexible(path) if path.exists() else ""
                self._send_text(content)
                return

            if parsed.path == "/api/logs":
                params = parse_qs(parsed.query)
                lines = int(params.get("lines", ["200"])[0])
                self._send_text(tail_lines(LOG_FILE, lines=lines))
                return

            if parsed.path == "/api/download":
                params = parse_qs(parsed.query)
                base = params.get("base", [""])[0]
                rel = params.get("path", [""])[0]
                inline = params.get("inline", ["0"])[0] == "1"
                base_dir = {"assets": ASSETS_DIR, "output": OUTPUT_DIR, "input": INPUT_DIR}.get(base)
                if not base_dir:
                    self._send_text("Invalid base", status=400)
                    return
                path = safe_path(base_dir, rel)
                self._send_file(path, inline=inline)
                return

            self._send_text("Not Found", status=404)
        except Exception as exc:
            logging.exception("GET error")
            self._send_text(f"Error: {exc}", status=500)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)

            if parsed.path == "/api/upload/assets":
                fields, files = self._parse_multipart()
                rel_dir = fields.get("dir", [""])[0]
                target_dir = safe_path(ASSETS_DIR, rel_dir)
                ensure_dir(target_dir)

                file_items = files.get("file", [])
                for item in file_items:
                    filename = item.get("filename")
                    if not filename:
                        continue
                    dest = safe_path(target_dir, Path(filename).name)
                    with dest.open("wb") as f:
                        f.write(item.get("data", b""))
                self._send_json({"ok": True})
                return

            if parsed.path.startswith("/api/upload/input"):
                params = parse_qs(parsed.query)
                force_name = params.get("force", [""])[0]
                fields, files = self._parse_multipart()
                items = files.get("file", [])
                item = items[0] if items else None
                if not item or not item.get("filename"):
                    self._send_text("No file", status=400)
                    return
                filename = force_name or Path(item["filename"]).name
                if filename != "config.yml" and not filename.endswith(".csv"):
                    self._send_text("Invalid filename", status=400)
                    return
                dest = safe_path(INPUT_DIR, filename)
                with dest.open("wb") as f:
                    f.write(item.get("data", b""))
                self._send_json({"ok": True, "filename": filename})
                return

            if parsed.path == "/api/rename/assets":
                data = self._parse_json()
                old = data.get("old", "")
                new = data.get("new", "")
                if not old or not new:
                    self._send_text("Missing fields", status=400)
                    return
                src = safe_path(ASSETS_DIR, old)
                dst = safe_path(ASSETS_DIR, new)
                ensure_dir(dst.parent)
                src.rename(dst)
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/delete/assets":
                data = self._parse_json()
                rel = data.get("path", "")
                if not rel:
                    self._send_text("Missing fields", status=400)
                    return
                target = safe_path(ASSETS_DIR, rel)
                if target.is_dir():
                    self._send_text("Cannot delete directory", status=400)
                    return
                if target.exists():
                    target.unlink()
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/text":
                data = self._parse_json()
                base = data.get("base")
                rel = data.get("path")
                content = data.get("content", "")
                if base != "input" or (rel != "config.yml" and not rel.endswith(".csv")):
                    self._send_text("Forbidden", status=403)
                    return
                path = safe_path(INPUT_DIR, rel)
                path.write_text(content, encoding="utf-8")
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/build":
                data = self._parse_json()
                csv_name = data.get("csv", "scenario.csv")
                csv_path = safe_path(INPUT_DIR, csv_name)
                if not csv_path.exists():
                    self._send_text("CSV not found", status=404)
                    return
                ensure_dir(OUTPUT_DIR)
                cmd = [
                    os.environ.get("PYTHON", sys.executable),
                    str(PROJECT_ROOT / "luminas_script.py"),
                    csv_name,
                ]
                logging.info("Build start: %s", csv_name)
                result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
                logging.info("Build stdout:\n%s", result.stdout.strip())
                if result.stderr:
                    logging.error("Build stderr:\n%s", result.stderr.strip())
                if result.returncode != 0:
                    self._send_text("Build failed", status=500)
                    return
                self._send_json({"ok": True, "message": "ビルド完了"})
                return

            self._send_text("Not Found", status=404)
        except Exception as exc:
            logging.exception("POST error")
            self._send_text(f"Error: {exc}", status=500)


def run_server(host: str = "0.0.0.0", port: int = 3000) -> None:
    ensure_dir(LOG_DIR)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )
    server = HTTPServer((host, port), GUIHandler)
    print(f"LuminousScript GUI running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
