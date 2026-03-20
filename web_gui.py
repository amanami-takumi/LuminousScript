#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple GUI server for LuminousScript (port 3000)."""

import io
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import sys
import zipfile
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
      --asset-tile-size: 96px;
      --asset-icon-size: 28px;
      --asset-media-max: 70px;
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
        "assets assets"
        "input input"
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

    input[type="range"] {
      accent-color: #2f384d;
      height: 4px;
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

    .list-item-main {
      min-width: 0;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .list-item-side {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-shrink: 0;
    }

    .list-item-size {
      min-width: 72px;
      text-align: right;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }

    .list-action-btn {
      padding: 4px 8px;
      font-size: 11px;
    }

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
      grid-template-columns: repeat(auto-fill, minmax(var(--asset-tile-size), 1fr));
    }

    .preview-tile {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px;
      background: #0e1421;
      transition: background-color 0.14s ease, border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease, filter 0.14s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 6px;
      cursor: pointer;
      text-align: center;
      min-height: var(--asset-tile-size);
    }

    .preview-tile:hover { background: #141c2a; }
    .preview-tile.active {
      background: #1b2638;
      border-color: #5d7298;
      outline: 2px solid #7f93bb;
      box-shadow: 0 0 0 1px rgba(127, 147, 187, 0.35), 0 10px 24px rgba(8, 12, 20, 0.35);
      transform: translateY(-1px);
    }
    .preview-tile.active img,
    .preview-tile.active audio,
    .preview-tile.active .preview-icon,
    .preview-tile.active .preview-name {
      filter: brightness(1.12);
    }
    .preview-tile.drop-target {
      outline: 2px dashed #5d7298;
      background: #182235;
    }
    .preview-tile.dragging {
      opacity: 0.55;
    }

    .preview-tile img, .preview-tile audio {
      max-width: 100%;
      max-height: var(--asset-media-max);
    }

    .preview-icon {
      font-size: var(--asset-icon-size);
      line-height: 1;
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

    .header-link {
      font-size: 11px;
      color: var(--muted);
      text-decoration: none;
      border: 1px solid var(--border);
      padding: 6px 10px;
      border-radius: 8px;
      background: #121826;
    }

    .header-link:hover {
      color: var(--text);
      border-color: #2f384d;
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

    .preview-modal {
      width: min(720px, 92vw);
    }

    .preview-title {
      font-size: 12px;
      font-weight: 600;
    }

    .preview-media {
      margin-top: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      background: #0C0A09;
      min-height: 220px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
    }

    .preview-media img {
      max-width: 100%;
      max-height: 60vh;
      border-radius: 8px;
    }

    .preview-media audio {
      width: min(520px, 100%);
    }

    .preview-meta {
      margin-top: 8px;
      font-size: 11px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }

    .preview-form {
      margin-top: 12px;
      display: grid;
      gap: 8px;
    }

    .preview-form label {
      font-size: 11px;
      color: var(--muted);
    }

    .preview-form .row {
      flex-wrap: nowrap;
    }

    .preview-form input {
      margin: 0;
    }

    .range-value {
      font-size: 11px;
      color: var(--muted);
      min-width: 62px;
      text-align: right;
    }

    .csv-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      table-layout: fixed;
      border: 1px solid #2a3347;
    }

    .csv-table th,
    .csv-table td {
      border: 1px solid #2a3347;
      padding: 0;
      background: #0C0A09;
    }

    .csv-table input {
      width: 100%;
      background: transparent;
      color: var(--text);
      border: none;
      border-radius: 0;
      padding: 6px 8px;
      font-size: 12px;
    }

    .csv-table th {
      background: #10151e;
      color: var(--muted);
      font-weight: 600;
      text-align: left;
    }

    footer {
      padding: 10px 24px 24px;
      color: var(--muted);
      font-size: 11px;
      text-align: center;
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
      <a class="header-link" href="https://github.com/amanami-takumi/LuminousScript" target="_blank" rel="noopener">GitHub</a>
      <button class="secondary" onclick="resetPassword()">パスワード再入力</button>
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

  <div class="overlay" id="assetPreviewOverlay" style="display:none">
    <div class="overlay-card preview-modal" onclick="event.stopPropagation()">
      <div class="row" style="justify-content: space-between;">
        <div class="preview-title" id="assetPreviewTitle">Preview</div>
        <button class="secondary" onclick="closeAssetPreview()">閉じる</button>
      </div>
      <div class="preview-media" id="assetPreviewMedia"></div>
      <div class="preview-meta" id="assetPreviewMeta"></div>
      <div class="preview-form">
        <label for="assetPreviewFilename">ファイル名</label>
        <div class="row">
          <input type="text" id="assetPreviewFilename" placeholder="example.png" />
          <button class="secondary" onclick="renameAssetFromPreview()">変更</button>
        </div>
      </div>
    </div>
  </div>

  <div class="overlay" id="inputEditorOverlay" style="display:none">
    <div class="overlay-card preview-modal" onclick="event.stopPropagation()">
      <div class="row" style="justify-content: space-between;">
        <div class="preview-title" id="inputEditorTitle">Editor</div>
        <div class="row">
          <button class="secondary" onclick="saveInputEditorModal()">保存</button>
          <button class="secondary" onclick="closeInputEditorModal()">閉じる</button>
        </div>
      </div>
      <div class="preview-media" id="inputEditorBody"></div>
    </div>
  </div>

  <div class="container">
    <section class="card assets-card">
      <h2>Assets 管理</h2>
      <div class="path" id="assetsPath"></div>
      <div class="muted">単クリックで選択、Shift+クリックで範囲選択、Ctrl+クリックで複数選択、ダブルクリックでフォルダを開くかファイルをプレビューします。</div>
      <div class="row">
        <span class="badge">アイコンサイズ</span>
        <input type="range" id="assetsIconSize" min="60" max="320" step="4" />
        <span class="range-value" id="assetsIconSizeValue">96px</span>
        <span class="badge" id="assetsSelectionInfo">未選択</span>
      </div>
      <div class="preview" id="assetsList"></div>
      <div class="row">
        <input type="file" id="assetsUpload" multiple style="display:none" />
        <button onclick="openAssetsPicker()">アップロード</button>
        <button class="secondary" onclick="createAssetDirectory()">フォルダ作成</button>
        <button class="secondary" onclick="downloadSelectedAsset()">ダウンロード</button>
        <button class="danger" onclick="deleteSelectedAsset()">削除</button>
        <button class="secondary" id="assetsCopyToggle" onclick="toggleAssetCopy()">コピー: OFF</button>
      </div>
      <div class="row">
        <input type="text" id="renameFrom" placeholder="old/path" />
        <input type="text" id="renameTo" placeholder="new/path" />
        <button class="secondary" onclick="renameAsset()">名前変更</button>
      </div>
    </section>

    <section class="card input-card">
      <h2>CSV / config.yml</h2>
      <div class="list" id="inputList"></div>
      <div class="row">
        <span class="badge" id="inputSelectedName">未選択</span>
        <button class="secondary" onclick="downloadSelectedInput()">ダウンロード</button>
        <button onclick="openInputEditorModal()">編集</button>
      </div>
      <div class="row">
        <input type="file" id="inputUpload" accept=".csv,.yml,.yaml" style="display:none" />
        <button onclick="openInputPicker()">アップロード</button>
      </div>
      <textarea id="inputEditor" placeholder="CSV / config.yml を編集" style="display:none"></textarea>
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
      <div class="row">
        <button class="secondary" onclick="checkSceneId()">scene_idチェック</button>
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

  <footer>Project Luminous / 天波たくみ（amanami-takumi） / 星海天測団</footer>

  <script>
    const state = {
      assetsDir: "",
      outputDir: "",
      assetsSelected: null,
      assetsSelectedKeys: [],
      assetsEntries: [],
      assetsSelectionAnchor: null,
      assetsPreview: null,
      assetsDragging: [],
      inputSelected: null,
      assetsCopyEnabled: false,
      assetsIconSize: 96,
    };

    const PASSWORD = "luminous";
    const PASSWORD_KEY = "luminous_gui_password";
    const ASSETS_ICON_SIZE_KEY = "luminous_assets_icon_size";

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
      const { includeParent = false, currentDir = "", onDoubleClick = null } = options;
      el.innerHTML = "";
      if (includeParent && currentDir) {
        const parent = document.createElement("div");
        parent.className = "list-item";
        parent.innerHTML = `<span class="list-item-main">📁 ..</span><span class="list-item-side"><span class="badge">dir</span></span>`;
        parent.onclick = () => onClick({ type: "dir", rel_path: parentPath(currentDir), name: ".." });
        if (onDoubleClick) parent.ondblclick = () => onDoubleClick({ type: "dir", rel_path: parentPath(currentDir), name: ".." });
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
        row.innerHTML = `<span class="list-item-main">${entry.type === "dir" ? "📁" : "📄"} ${entry.name}</span><span class="list-item-side"><span class="badge">${entry.type}</span></span>`;
        row.onclick = () => onClick(entry);
        if (onDoubleClick) row.ondblclick = () => onDoubleClick(entry);
        el.appendChild(row);
      });
    }

    function renderOutputList(el, entries, currentDir = "") {
      el.innerHTML = "";
      if (currentDir) {
        const parent = document.createElement("div");
        parent.className = "list-item";
        parent.innerHTML = `
          <span class="list-item-main">📁 ..</span>
          <span class="list-item-side">
            <span class="list-item-size">-</span>
            <span class="badge">dir</span>
          </span>
        `;
        parent.onclick = () => {
          state.outputDir = parentPath(currentDir);
          refreshOutput();
        };
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

        const name = document.createElement("span");
        name.className = "list-item-main";
        name.textContent = `${entry.type === "dir" ? "📁" : "📄"} ${entry.name}`;
        row.appendChild(name);

        const side = document.createElement("span");
        side.className = "list-item-side";

        const size = document.createElement("span");
        size.className = "list-item-size";
        size.textContent = entry.type === "file" ? formatBytes(entry.size) : "-";
        side.appendChild(size);

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = entry.type;
        side.appendChild(badge);

        const deleteButton = document.createElement("button");
        deleteButton.className = "danger list-action-btn";
        deleteButton.textContent = "削除";
        deleteButton.onclick = async (event) => {
          event.stopPropagation();
          await deleteOutputEntry(entry);
        };
        side.appendChild(deleteButton);

        row.appendChild(side);
        row.onclick = () => {
          if (entry.type === "dir") {
            state.outputDir = entry.rel_path;
            refreshOutput();
          } else {
            window.open(`/api/download?base=output&path=${encodeURIComponent(entry.rel_path)}`, "_blank");
          }
        };
        el.appendChild(row);
      });
    }

    function parentPath(path) {
      const parts = path.split("/").filter(Boolean);
      parts.pop();
      return parts.join("/");
    }

    function joinAssetPath(dir, name) {
      return normalizeRelPath(dir ? `${dir}/${name}` : name);
    }

    function normalizeRelPath(path) {
      const normalized = `${path || ""}`.replace(/\\/g, "/");
      const parts = [];
      for (const part of normalized.split("/")) {
        if (!part || part === ".") continue;
        if (part === "..") {
          throw new Error("親ディレクトリは指定できません");
        }
        parts.push(part);
      }
      return parts.join("/");
    }

    function formatBytes(bytes) {
      if (!Number.isFinite(bytes)) return "-";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let value = bytes;
      let index = 0;
      while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index += 1;
      }
      const precision = value >= 10 || index === 0 ? 0 : 1;
      return `${value.toFixed(precision)} ${units[index]}`;
    }

    function updateAssetCopyButton() {
      const button = document.getElementById("assetsCopyToggle");
      if (!button) return;
      button.textContent = state.assetsCopyEnabled ? "コピー: ON" : "コピー: OFF";
    }

    function assetEntryKey(entry) {
      if (!entry) return "";
      return `${entry.type}:${entry.rel_path}`;
    }

    function isAssetEntrySelected(entry) {
      const key = assetEntryKey(entry);
      return Boolean(key) && state.assetsSelectedKeys.includes(key);
    }

    function getAssetSelectedEntries() {
      const selected = state.assetsEntries.filter((entry) => isAssetEntrySelected(entry));
      if (state.assetsSelected && !selected.some((entry) => assetEntryKey(entry) === assetEntryKey(state.assetsSelected))) {
        state.assetsSelected = selected[0] || null;
      }
      return selected;
    }

    function syncAssetRenameFields() {
      const renameFrom = document.getElementById("renameFrom");
      const renameTo = document.getElementById("renameTo");
      const selectedEntries = getAssetSelectedEntries();
      if (selectedEntries.length === 1) {
        renameFrom.value = selectedEntries[0].rel_path;
        renameTo.value = selectedEntries[0].rel_path;
      } else {
        renameFrom.value = "";
        renameTo.value = "";
      }
    }

    function updateAssetsSelectionInfo() {
      const info = document.getElementById("assetsSelectionInfo");
      if (!info) return;
      const selectedEntries = getAssetSelectedEntries();
      if (!selectedEntries.length) {
        info.textContent = "未選択";
        return;
      }
      const fileCount = selectedEntries.filter((entry) => entry.type === "file").length;
      const dirCount = selectedEntries.filter((entry) => entry.type === "dir").length;
      info.textContent = `${selectedEntries.length}件選択 (${fileCount} file / ${dirCount} dir)`;
    }

    function syncAssetSelectionUI() {
      const tiles = document.querySelectorAll(".preview-tile");
      tiles.forEach((tile) => {
        const key = `${tile.dataset.type}:${tile.dataset.path}`;
        tile.classList.toggle("active", state.assetsSelectedKeys.includes(key));
      });
      syncAssetRenameFields();
      updateAssetsSelectionInfo();
    }

    function setAssetSelection(entries, anchorEntry = null) {
      const normalized = [];
      const seen = new Set();
      entries.forEach((entry) => {
        if (!entry || entry.name === "..") return;
        const key = assetEntryKey(entry);
        if (!key || seen.has(key)) return;
        seen.add(key);
        normalized.push(entry);
      });
      state.assetsSelectedKeys = normalized.map((entry) => assetEntryKey(entry));
      state.assetsSelected = normalized.length === 1 ? normalized[0] : (anchorEntry || normalized[normalized.length - 1] || null);
      state.assetsSelectionAnchor = anchorEntry || state.assetsSelected || null;
      syncAssetSelectionUI();
      if (state.assetsCopyEnabled && normalized.length === 1 && normalized[0]?.type === "file") {
        copyAssetBasename(normalized[0]);
      }
    }

    function clearAssetSelection() {
      state.assetsSelectedKeys = [];
      state.assetsSelected = null;
      state.assetsSelectionAnchor = null;
      syncAssetSelectionUI();
    }

    function getAssetEntryRange(fromEntry, toEntry) {
      const fromIndex = state.assetsEntries.findIndex((entry) => assetEntryKey(entry) === assetEntryKey(fromEntry));
      const toIndex = state.assetsEntries.findIndex((entry) => assetEntryKey(entry) === assetEntryKey(toEntry));
      if (fromIndex < 0 || toIndex < 0) return [toEntry];
      const start = Math.min(fromIndex, toIndex);
      const end = Math.max(fromIndex, toIndex);
      return state.assetsEntries.slice(start, end + 1);
    }

    function handleAssetTileClick(entry, event) {
      if (!entry || entry.name === "..") return;
      const toggleSelection = event.ctrlKey || event.metaKey;
      if (event.shiftKey && state.assetsSelectionAnchor) {
        const rangeEntries = getAssetEntryRange(state.assetsSelectionAnchor, entry);
        if (toggleSelection) {
          const merged = [...getAssetSelectedEntries(), ...rangeEntries];
          setAssetSelection(merged, entry);
        } else {
          setAssetSelection(rangeEntries, state.assetsSelectionAnchor);
        }
        return;
      }
      if (toggleSelection) {
        if (isAssetEntrySelected(entry)) {
          const remaining = getAssetSelectedEntries().filter((item) => assetEntryKey(item) !== assetEntryKey(entry));
          setAssetSelection(remaining, remaining[remaining.length - 1] || null);
        } else {
          setAssetSelection([...getAssetSelectedEntries(), entry], entry);
        }
        return;
      }
      setAssetSelection([entry], entry);
    }

    function applyAssetsIconSize(value) {
      const size = Math.max(60, Math.min(320, Number(value) || 96));
      state.assetsIconSize = size;
      const iconSize = Math.max(18, Math.round(size * 0.3));
      const mediaSize = Math.max(40, Math.round(size * 0.75));
      document.documentElement.style.setProperty("--asset-tile-size", `${size}px`);
      document.documentElement.style.setProperty("--asset-icon-size", `${iconSize}px`);
      document.documentElement.style.setProperty("--asset-media-max", `${mediaSize}px`);
      const label = document.getElementById("assetsIconSizeValue");
      if (label) label.textContent = `${size}px`;
    }

    function loadAssetsIconSize() {
      const saved = Number(localStorage.getItem(ASSETS_ICON_SIZE_KEY));
      const initial = Number.isFinite(saved) && saved > 0 ? saved : state.assetsIconSize;
      const slider = document.getElementById("assetsIconSize");
      if (slider) slider.value = String(initial);
      applyAssetsIconSize(initial);
    }

    function handleAssetsIconSizeChange(event) {
      const value = Number(event.target.value);
      applyAssetsIconSize(value);
      localStorage.setItem(ASSETS_ICON_SIZE_KEY, String(state.assetsIconSize));
    }

    function toggleAssetCopy() {
      state.assetsCopyEnabled = !state.assetsCopyEnabled;
      updateAssetCopyButton();
    }

    async function copyAssetBasename(entry) {
      if (!entry || entry.type !== "file") return;
      const name = entry.name || "";
      const base = name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name;
      try {
        await navigator.clipboard.writeText(base);
      } catch (err) {
        alert("クリップボードにコピーできませんでした");
      }
    }

    async function refreshAssets() {
      const data = await apiGet("/api/assets/list", { dir: state.assetsDir });
      if (data.dir !== undefined) {
        state.assetsDir = data.dir || "";
      }
      state.assetsEntries = data.entries || [];
      state.assetsSelectedKeys = state.assetsSelectedKeys.filter((key) => (
        state.assetsEntries.some((entry) => assetEntryKey(entry) === key)
      ));
      state.assetsSelected = state.assetsEntries.find((entry) => isAssetEntrySelected(entry)) || null;
      if (state.assetsSelectionAnchor && !state.assetsEntries.some((entry) => (
        assetEntryKey(entry) === assetEntryKey(state.assetsSelectionAnchor)
      ))) {
        state.assetsSelectionAnchor = state.assetsSelected || null;
      }
      document.getElementById("assetsPath").textContent = `input/assets/${data.dir || ""}`;
      renderAssetsExplorer(document.getElementById("assetsList"), data.entries, {
        includeParent: true,
        currentDir: data.dir,
      });
    }

    function renderAssetsExplorer(container, entries, options = {}) {
      const { includeParent = false, currentDir = "" } = options;
      container.innerHTML = "";
      const grid = document.createElement("div");
      grid.className = "preview-grid";

      if (includeParent && currentDir) {
        const parentEntry = { type: "dir", rel_path: parentPath(currentDir), name: ".." };
        const parent = document.createElement("div");
        parent.className = "preview-tile";
        parent.dataset.type = parentEntry.type;
        parent.dataset.path = parentEntry.rel_path;
        parent.dataset.dropDir = parentEntry.rel_path;
        parent.innerHTML = `<div class="preview-icon">📁</div><div class="preview-name">..</div>`;
        parent.onclick = () => clearAssetSelection();
        parent.ondblclick = () => {
          state.assetsDir = parentEntry.rel_path;
          refreshAssets();
        };
        attachAssetDropTarget(parent, parentEntry.rel_path);
        grid.appendChild(parent);
      }

      if (!entries.length && !(includeParent && currentDir)) {
        const empty = document.createElement("div");
        empty.className = "muted";
        empty.textContent = "空";
        container.appendChild(empty);
        return;
      }

      entries.forEach((entry) => {
        const tile = document.createElement("div");
        tile.className = "preview-tile";
        tile.dataset.path = entry.rel_path;
        tile.dataset.type = entry.type;
        if (entry.type === "dir") {
          tile.dataset.dropDir = entry.rel_path;
          tile.innerHTML = `<div class="preview-icon">📁</div><div class="preview-name">${entry.name}</div>`;
          tile.draggable = true;
          tile.onclick = (event) => handleAssetTileClick(entry, event);
          tile.ondblclick = () => {
            setAssetSelection([entry], entry);
            state.assetsDir = entry.rel_path;
            refreshAssets();
          };
          tile.ondragstart = (event) => handleAssetDragStart(event, entry);
          tile.ondragend = () => handleAssetDragEnd();
          attachAssetDropTarget(tile, entry.rel_path);
        } else {
          const url = `/api/download?base=assets&path=${encodeURIComponent(entry.rel_path)}&inline=1`;
          const ext = entry.name.split(".").pop().toLowerCase();
          if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
            tile.innerHTML = `<img src="${url}" alt="${entry.name}" /><div class="preview-name">${entry.name}</div>`;
          } else if (["mp3", "wav", "ogg"].includes(ext)) {
            tile.innerHTML = `<div class="preview-icon">🎵</div><div class="preview-name">${entry.name}</div>`;
          } else {
            tile.innerHTML = `<div class="preview-icon">📄</div><div class="preview-name">${entry.name}</div>`;
          }
          tile.draggable = true;
          tile.onclick = (event) => handleAssetTileClick(entry, event);
          tile.ondblclick = () => {
            setAssetSelection([entry], entry);
            openAssetPreview(entry);
          };
          tile.ondragstart = (event) => handleAssetDragStart(event, entry);
          tile.ondragend = () => handleAssetDragEnd();
        }
        grid.appendChild(tile);
      });

      container.appendChild(grid);
      syncAssetSelectionUI();
    }

    function handleAssetDragStart(event, entry) {
      let dragEntries = getAssetSelectedEntries();
      if (!isAssetEntrySelected(entry)) {
        setAssetSelection([entry], entry);
        dragEntries = [entry];
      }
      state.assetsDragging = dragEntries.filter((item) => item.name !== "..");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", JSON.stringify(state.assetsDragging.map((item) => item.rel_path)));
      }
      document.querySelectorAll(".preview-tile").forEach((tile) => {
        const key = `${tile.dataset.type}:${tile.dataset.path}`;
        tile.classList.toggle("dragging", state.assetsDragging.some((item) => assetEntryKey(item) === key));
      });
    }

    function handleAssetDragEnd() {
      state.assetsDragging = [];
      document.querySelectorAll(".preview-tile").forEach((node) => {
        node.classList.remove("dragging");
        node.classList.remove("drop-target");
      });
    }

    function attachAssetDropTarget(tile, targetDir) {
      tile.ondragover = (event) => {
        if (!state.assetsDragging.length) return;
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
        tile.classList.add("drop-target");
      };
      tile.ondragleave = () => {
        tile.classList.remove("drop-target");
      };
      tile.ondrop = async (event) => {
        if (!state.assetsDragging.length) return;
        event.preventDefault();
        tile.classList.remove("drop-target");
        const sourceEntries = [...state.assetsDragging];
        state.assetsDragging = [];
        await moveAssetsToDirectory(sourceEntries, targetDir);
        handleAssetDragEnd();
      };
    }

    async function moveAssetsToDirectory(entries, targetDir) {
      const selectedEntries = (entries || []).filter(Boolean);
      if (!selectedEntries.length) return;
      const normalizedTarget = normalizeRelPath(targetDir);
      const movablePaths = selectedEntries.map((entry) => entry.rel_path);
      if (!movablePaths.length) return;
      await apiPost("/api/move/assets", { paths: movablePaths, target_dir: normalizedTarget });
      clearAssetSelection();
      await refreshAssets();
    }

    function openAssetPreview(entry) {
      if (!entry || entry.type !== "file") return;
      setAssetSelection([entry], entry);
      state.assetsPreview = entry;
      const overlay = document.getElementById("assetPreviewOverlay");
      const title = document.getElementById("assetPreviewTitle");
      const media = document.getElementById("assetPreviewMedia");
      const meta = document.getElementById("assetPreviewMeta");
      const filenameInput = document.getElementById("assetPreviewFilename");
      const sizeText = formatBytes(entry.size);
      const url = `/api/download?base=assets&path=${encodeURIComponent(entry.rel_path)}&inline=1`;
      const ext = entry.name.split(".").pop().toLowerCase();

      title.textContent = entry.name;
      media.innerHTML = "";
      meta.innerHTML = "";
      filenameInput.value = entry.name;
      const sizeSpan = document.createElement("span");
      sizeSpan.textContent = `サイズ: ${sizeText}`;
      const dimSpan = document.createElement("span");
      dimSpan.textContent = "寸法: -";
      const dirSpan = document.createElement("span");
      dirSpan.textContent = `ディレクトリ: ${parentPath(entry.rel_path) || "."}`;
      meta.appendChild(sizeSpan);
      meta.appendChild(dimSpan);
      meta.appendChild(dirSpan);

      if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
        const img = new Image();
        img.onload = () => {
          dimSpan.textContent = `寸法: ${img.naturalWidth} x ${img.naturalHeight}`;
        };
        img.src = url;
        media.appendChild(img);
      } else if (["mp3", "wav", "ogg"].includes(ext)) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.src = url;
        media.appendChild(audio);
      } else {
        const icon = document.createElement("div");
        icon.className = "preview-icon";
        icon.textContent = "📄";
        const name = document.createElement("div");
        name.className = "preview-name";
        name.textContent = entry.name;
        media.appendChild(icon);
        media.appendChild(name);
      }

      overlay.style.display = "flex";
    }

    function closeAssetPreview() {
      const overlay = document.getElementById("assetPreviewOverlay");
      overlay.style.display = "none";
      state.assetsPreview = null;
    }

    function parseCsv(text) {
      const rows = [];
      let row = [];
      let value = "";
      let inQuotes = false;
      for (let i = 0; i < text.length; i += 1) {
        const char = text[i];
        const next = text[i + 1];
        if (inQuotes) {
          if (char === "\"" && next === "\"") {
            value += "\"";
            i += 1;
          } else if (char === "\"") {
            inQuotes = false;
          } else {
            value += char;
          }
          continue;
        }
        if (char === "\"") {
          inQuotes = true;
          continue;
        }
        if (char === ",") {
          row.push(value);
          value = "";
          continue;
        }
        if (char === "\n") {
          row.push(value);
          rows.push(row);
          row = [];
          value = "";
          continue;
        }
        if (char === "\r") {
          continue;
        }
        value += char;
      }
      row.push(value);
      rows.push(row);
      if (rows.length === 1 && rows[0].length === 1 && rows[0][0] === "") return [];
      return rows;
    }

    function serializeCsv(rows) {
      return rows.map((row) => row.map((cell) => {
        const text = `${cell ?? ""}`;
        if (/[",\n\r]/.test(text)) {
          return `"${text.replace(/"/g, "\"\"")}"`;
        }
        return text;
      }).join(",")).join("\n");
    }

    function buildCsvTable(rows) {
      const table = document.createElement("table");
      table.className = "csv-table";
      const tbody = document.createElement("tbody");
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        row.forEach((cell) => {
          const td = document.createElement("td");
          const input = document.createElement("input");
          input.type = "text";
          input.value = cell ?? "";
          td.appendChild(input);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      return table;
    }

    async function openInputEditorModal(entry = null) {
      if (entry) {
        state.inputSelected = entry;
        document.getElementById("inputSelectedName").textContent = entry.name;
        if (entry.name === "config.yml" || entry.name.endsWith(".csv")) {
          await loadInputText(entry.name);
        }
      }
      if (!state.inputSelected) return alert("ファイルを選択してください");
      const overlay = document.getElementById("inputEditorOverlay");
      const title = document.getElementById("inputEditorTitle");
      const body = document.getElementById("inputEditorBody");
      const content = document.getElementById("inputEditor").value;
      const isCsv = state.inputSelected.name.endsWith(".csv");

      title.textContent = state.inputSelected.name;
      body.innerHTML = "";
      body.style.alignItems = "stretch";
      body.style.justifyContent = "flex-start";
      body.style.overflow = "auto";
      if (isCsv) {
        const rows = parseCsv(content);
        if (!rows.length) rows.push([""]);
        const table = buildCsvTable(rows);
        table.id = "csvEditorTable";
        body.appendChild(table);
      } else {
        const textarea = document.createElement("textarea");
        textarea.id = "inputEditorModalText";
        textarea.value = content;
        textarea.style.width = "100%";
        textarea.style.height = "320px";
        body.appendChild(textarea);
      }
      overlay.style.display = "flex";
    }

    function closeInputEditorModal() {
      const overlay = document.getElementById("inputEditorOverlay");
      overlay.style.display = "none";
    }

    async function saveInputEditorModal() {
      if (!state.inputSelected) return alert("ファイルを選択してください");
      const isCsv = state.inputSelected.name.endsWith(".csv");
      if (isCsv) {
        const table = document.getElementById("csvEditorTable");
        const rows = Array.from(table.querySelectorAll("tr")).map((tr) => (
          Array.from(tr.querySelectorAll("input")).map((input) => input.value)
        ));
        document.getElementById("inputEditor").value = serializeCsv(rows);
      } else {
        const textarea = document.getElementById("inputEditorModalText");
        document.getElementById("inputEditor").value = textarea.value;
      }
      await saveInputText();
      closeInputEditorModal();
    }

    async function downloadSelectedAsset() {
      const selectedEntries = getAssetSelectedEntries();
      if (!selectedEntries.length) return alert("ファイルを選択してください");
      if (selectedEntries.length === 1 && selectedEntries[0].type === "file") {
        window.open(`/api/download?base=assets&path=${encodeURIComponent(selectedEntries[0].rel_path)}`, "_blank");
        return;
      }
      const url = new URL("/api/download/assets-batch", window.location.origin);
      selectedEntries.forEach((entry) => url.searchParams.append("path", entry.rel_path));
      const res = await fetch(url);
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const header = res.headers.get("Content-Disposition") || "";
      const match = header.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || "assets_bundle.zip";
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    }

    async function deleteSelectedAsset() {
      const selectedEntries = getAssetSelectedEntries();
      if (!selectedEntries.length) return alert("対象を選択してください");
      const targetList = selectedEntries.map((entry) => entry.rel_path).join("\\n");
      if (!confirm(`削除しますか？\\n${targetList}`)) return;
      await apiPost("/api/delete/assets-batch", { paths: selectedEntries.map((entry) => entry.rel_path) });
      clearAssetSelection();
      await refreshAssets();
    }

    async function createAssetDirectory() {
      const name = prompt("作成するフォルダ名を入力してください", "");
      if (name === null) return;
      let relPath;
      try {
        relPath = joinAssetPath(state.assetsDir, name.trim());
      } catch (err) {
        alert(err.message);
        return;
      }
      if (!relPath) return alert("フォルダ名を入力してください");
      await apiPost("/api/mkdir/assets", { path: relPath });
      await refreshAssets();
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
      let oldPath;
      let newPath;
      try {
        oldPath = normalizeRelPath(document.getElementById("renameFrom").value.trim());
        newPath = normalizeRelPath(document.getElementById("renameTo").value.trim());
      } catch (err) {
        alert(err.message);
        return;
      }
      if (!oldPath || !newPath) return alert("旧/新パスを入力してください");
      await apiPost("/api/rename/assets", { old: oldPath, new: newPath });
      document.getElementById("renameFrom").value = "";
      document.getElementById("renameTo").value = "";
      clearAssetSelection();
      await refreshAssets();
    }

    async function renameAssetFromPreview() {
      const entry = state.assetsPreview;
      if (!entry || entry.type !== "file") return alert("ファイルを開いてください");
      const filenameInput = document.getElementById("assetPreviewFilename");
      const newName = filenameInput.value.trim();
      if (!newName) return alert("ファイル名を入力してください");
      if (newName === "." || newName === ".." || newName.includes("/") || newName.includes("\\")) {
        return alert("ファイル名のみ変更できます");
      }
      if (newName === entry.name) return;

      const currentDir = parentPath(entry.rel_path);
      const newPath = joinAssetPath(currentDir, newName);
      await apiPost("/api/rename/assets", { old: entry.rel_path, new: newPath });

      const updatedEntry = {
        ...entry,
        name: newName,
        rel_path: newPath,
      };
      state.assetsPreview = updatedEntry;
      setAssetSelection([updatedEntry], updatedEntry);
      await refreshAssets();
      openAssetPreview(updatedEntry);
    }

    async function refreshInput() {
      const data = await apiGet("/api/input/list");
      const list = document.getElementById("inputList");
      renderList(list, data.entries, (entry) => {
        if (entry.type === "file") {
          selectInput(entry);
        }
      }, { onDoubleClick: (entry) => {
        if (entry.type === "file") {
          openInputEditorModal(entry);
        }
      }});
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

    function openInputPicker() {
      const input = document.getElementById("inputUpload");
      input.click();
    }

    async function uploadInput() {
      const input = document.getElementById("inputUpload");
      if (!input.files.length) return;
      const file = input.files[0];
      const name = (file.name || "").toLowerCase();
      let endpoint = "/api/upload/input";
      if (name.endsWith(".yml") || name.endsWith(".yaml")) {
        endpoint = "/api/upload/input?force=config.yml";
      } else if (!name.endsWith(".csv")) {
        alert("CSV か config.yml を選択してください");
        input.value = "";
        return;
      }
      const form = new FormData();
      form.append("file", file);
      await apiPost(endpoint, form, false);
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
      state.outputDir = data.dir || "";
      document.getElementById("outputPath").textContent = `output/${data.dir || ""}`;
      renderOutputList(document.getElementById("outputList"), data.entries, data.dir || "");
    }

    async function deleteOutputEntry(entry) {
      if (!entry) return;
      const targetLabel = entry.type === "dir" ? `フォルダ「${entry.name}」` : `ファイル「${entry.name}」`;
      if (!window.confirm(`${targetLabel}を削除します。よろしいですか？`)) return;
      await apiPost("/api/delete/output", { path: entry.rel_path });
      await refreshOutput();
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

    async function checkSceneId() {
      const csv = document.getElementById("buildCsv").value;
      if (!csv) return alert("CSVを選択してください");
      setStatus("scene_idチェック中...");
      try {
        const result = await apiPost("/api/check_scene_id", { csv });
        setStatus(result.message || "チェック完了");
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
      document.getElementById("inputUpload").addEventListener("change", uploadInput);
      document.getElementById("assetPreviewOverlay").addEventListener("click", closeAssetPreview);
      document.getElementById("inputEditorOverlay").addEventListener("click", closeInputEditorModal);
      document.getElementById("assetsIconSize").addEventListener("input", handleAssetsIconSizeChange);
      document.getElementById("assetsIconSize").addEventListener("change", handleAssetsIconSizeChange);
      updateAssetCopyButton();
      loadAssetsIconSize();
      await ensurePassword();
    }

    init().catch((err) => alert(err.message));
  </script>
</body>
</html>
"""


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_rel_path(rel: str) -> str:
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel:
        return ""
    parts = []
    for part in rel.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError("Invalid path")
        parts.append(part)
    return "/".join(parts)


def safe_path(base: Path, rel: str) -> Path:
    rel = normalize_rel_path(rel)
    target = (base / rel).resolve()
    base_resolved = base.resolve()
    if str(target) == str(base_resolved):
        return target
    if not str(target).startswith(str(base_resolved) + os.sep):
        raise ValueError("Invalid path")
    return target


def list_dir(base: Path, rel: str) -> dict:
    rel = normalize_rel_path(rel)
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


def prune_nested_rel_paths(paths) -> list[str]:
    normalized = []
    seen = set()
    for rel in paths or []:
        cleaned = normalize_rel_path(rel)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    normalized.sort(key=lambda rel: (len(Path(rel).parts), rel))
    pruned = []
    for rel in normalized:
        if any(rel == existing or rel.startswith(f"{existing}/") for existing in pruned):
            continue
        pruned.append(rel)
    return pruned


def build_assets_archive(paths) -> tuple[bytes, str]:
    rel_paths = prune_nested_rel_paths(paths)
    if not rel_paths:
        raise ValueError("No paths")

    archive_name = "assets_bundle.zip" if len(rel_paths) > 1 else f"{Path(rel_paths[0]).name}.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in rel_paths:
            source = safe_path(ASSETS_DIR, rel)
            if not source.exists():
                raise FileNotFoundError(rel)
            if source.is_dir():
                children = sorted(source.rglob("*"))
                if not children:
                    archive.writestr(f"{rel}/", b"")
                    continue
                for child in children:
                    arcname = child.relative_to(ASSETS_DIR).as_posix()
                    if child.is_dir():
                        if not any(child.iterdir()):
                            archive.writestr(f"{arcname}/", b"")
                        continue
                    archive.write(child, arcname=arcname)
            else:
                archive.write(source, arcname=rel)
    return buffer.getvalue(), archive_name


def move_assets(paths, target_dir: str) -> int:
    rel_paths = prune_nested_rel_paths(paths)
    if not rel_paths:
        return 0

    target_rel = normalize_rel_path(target_dir)
    target = safe_path(ASSETS_DIR, target_rel)
    ensure_dir(target)
    if not target.is_dir():
        raise ValueError("Target must be directory")

    moves = []
    destinations = set()
    for rel in rel_paths:
        source = safe_path(ASSETS_DIR, rel)
        if not source.exists():
            raise FileNotFoundError(rel)
        destination = safe_path(ASSETS_DIR, str((Path(target_rel) / source.name).as_posix()) if target_rel else source.name)
        if source == destination:
            continue
        if source.parent == destination.parent:
            continue
        if source.is_dir():
            try:
                destination.relative_to(source)
            except ValueError:
                pass
            else:
                raise ValueError(f"Cannot move directory into itself: {rel}")
        if destination.exists():
            raise FileExistsError(destination.name)
        destination_rel = destination.relative_to(ASSETS_DIR).as_posix()
        if destination_rel in destinations:
            raise FileExistsError(destination.name)
        destinations.add(destination_rel)
        moves.append((source, destination))

    for source, destination in moves:
        ensure_dir(destination.parent)
        source.rename(destination)
    return len(moves)


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

    def _send_bytes(self, data: bytes, filename: str, content_type: str = "application/octet-stream", inline: bool = False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f"{disposition}; filename=\"{filename}\"")
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

            if parsed.path == "/api/download/assets-batch":
                params = parse_qs(parsed.query)
                paths = params.get("path", [])
                archive, filename = build_assets_archive(paths)
                self._send_bytes(archive, filename, content_type="application/zip")
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

            if parsed.path == "/api/mkdir/assets":
                data = self._parse_json()
                rel = data.get("path", "")
                if not rel:
                    self._send_text("Missing fields", status=400)
                    return
                target = safe_path(ASSETS_DIR, rel)
                ensure_dir(target)
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
                if not src.exists():
                    self._send_text("Source not found", status=404)
                    return
                if dst.exists():
                    self._send_text("Destination already exists", status=409)
                    return
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
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/delete/assets-batch":
                data = self._parse_json()
                paths = prune_nested_rel_paths(data.get("paths", []))
                if not paths:
                    self._send_text("Missing fields", status=400)
                    return
                for rel in reversed(paths):
                    target = safe_path(ASSETS_DIR, rel)
                    if not target.exists():
                        continue
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                self._send_json({"ok": True, "count": len(paths)})
                return

            if parsed.path == "/api/delete/output":
                data = self._parse_json()
                rel = data.get("path", "")
                if not rel:
                    self._send_text("Missing fields", status=400)
                    return
                target = safe_path(OUTPUT_DIR, rel)
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/move/assets":
                data = self._parse_json()
                paths = data.get("paths", [])
                target_dir = data.get("target_dir", "")
                moved = move_assets(paths, target_dir)
                self._send_json({"ok": True, "count": moved})
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

            if parsed.path == "/api/check_scene_id":
                data = self._parse_json()
                csv_name = data.get("csv", "scenario.csv")
                csv_path = safe_path(INPUT_DIR, csv_name)
                if not csv_path.exists():
                    self._send_text("CSV not found", status=404)
                    return
                cmd = [
                    os.environ.get("PYTHON", sys.executable),
                    str(PROJECT_ROOT / "check_scene_id.py"),
                    csv_name,
                ]
                logging.info("Scene ID check start: %s", csv_name)
                result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
                stdout = (result.stdout or "").strip()
                if stdout:
                    logging.info("Scene ID check stdout:\n%s", stdout)
                if result.stderr:
                    logging.error("Scene ID check stderr:\n%s", result.stderr.strip())
                if result.returncode != 0:
                    self._send_text("Scene ID check failed", status=500)
                    return
                self._send_json({"ok": True, "message": "scene_idチェック完了"})
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
