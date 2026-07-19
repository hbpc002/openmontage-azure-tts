#!/usr/bin/env python3
"""OpenMontage File Manager — browse, upload, delete, rename, create dirs."""

import json
import os
import mimetypes
import shutil
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT = int(os.environ.get("FM_PORT", "9090"))

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenMontage File Manager</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header h1{font-size:18px;color:#58a6ff;display:flex;align-items:center;gap:6px;margin-right:8px}
header .path{font-size:13px;color:#8b949e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;padding:4px 10px;background:#0d1117;border-radius:6px;border:1px solid #21262d}
.container{max-width:1280px;margin:0 auto;padding:16px 24px}
@media(max-width:768px){.container{padding:12px 12px}th,td{padding:6px 6px;font-size:13px}td.date,th:nth-child(4){display:none}td.icon{width:24px;font-size:14px}td.size{width:60px}td.actions{width:60px}}
.toolbar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.toolbar button,.toolbar label.btn{padding:6px 14px;border:1px solid #30363d;border-radius:6px;background:#21262d;color:#c9d1d9;cursor:pointer;font-size:13px;white-space:nowrap;transition:background .15s,border-color .15s;display:inline-flex;align-items:center;gap:4px}
.toolbar button:hover,.toolbar label.btn:hover{background:#30363d;border-color:#484f58}
.toolbar button:active,.toolbar label.btn:active{transform:translateY(1px)}
.toolbar button.danger{color:#f85149;border-color:#f85149}
.toolbar button.danger:hover{background:#f851491a}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #21262d;font-size:14px}
th{color:#8b949e;font-weight:600;position:sticky;top:0;background:#0d1117;user-select:none}
tr{transition:background .1s}
tr:hover td{background:#161b22}
td.icon{width:32px;font-size:16px;text-align:center}
td.name{word-break:break-word;overflow-wrap:break-word;line-height:1.4}
td.name a{color:#58a6ff;text-decoration:none;display:inline;vertical-align:top}
td.name a:hover{color:#79c0ff;text-decoration:underline}
.dir td.name a{font-weight:500}
td.size{color:#8b949e;white-space:nowrap;width:90px;text-align:right}
td.date{color:#8b949e;white-space:nowrap;width:150px}
td.actions{white-space:nowrap;width:90px;text-align:right}
td.actions button{padding:3px 8px;border:1px solid transparent;border-radius:4px;background:transparent;color:#8b949e;cursor:pointer;font-size:13px;transition:all .15s}
td.actions button:hover{background:#30363d;color:#c9d1d9;border-color:#30363d}
td.actions button.del:hover{color:#f85149;border-color:#f8514940;background:#f8514910}
.empty{text-align:center;padding:60px 24px;color:#484f58;font-size:14px;display:none}
.empty::before{content:'📂';display:block;font-size:32px;margin-bottom:12px}
#progress{position:fixed;bottom:20px;right:20px;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 20px;display:none;font-size:13px;z-index:100;min-width:240px;box-shadow:0 8px 24px #00000040}
#progress .bar{width:100%;height:5px;background:#30363d;border-radius:3px;margin-top:8px;overflow:hidden}
#progress .fill{height:100%;background:#2ea043;width:0;transition:width .3s ease;border-radius:3px}
.modal-overlay{display:none;position:fixed;inset:0;background:#00000080;z-index:200;justify-content:center;align-items:center}
.modal-overlay.active{display:flex}
.modal{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;min-width:360px;max-width:480px;box-shadow:0 16px 48px #00000060}
.modal h3{margin-bottom:16px;font-size:16px;font-weight:600}
.modal input{width:100%;padding:10px 12px;border:1px solid #30363d;border-radius:6px;background:#0d1117;color:#c9d1d9;font-size:14px;outline:none;transition:border-color .15s}
.modal input:focus{border-color:#58a6ff}
.modal .btns{display:flex;gap:8px;justify-content:flex-end;margin-top:4px}
.modal .btns button{padding:7px 18px;border:1px solid #30363d;border-radius:6px;cursor:pointer;font-size:13px;transition:background .15s}
.modal .btns .primary{background:#238636;border-color:#238636;color:#fff;font-weight:500}
.modal .btns .primary:hover{background:#2ea043}
.modal .btns .cancel{background:#21262d;color:#c9d1d9}
.modal .btns .cancel:hover{background:#30363d}
#upload-input{display:none}
footer{text-align:center;padding:20px;color:#484f58;font-size:12px;border-top:1px solid #21262d;margin-top:24px}
footer code{color:#8b949e;background:#161b22;padding:1px 6px;border-radius:4px;font-size:11px}
</style>
</head>
<body>
<header>
  <h1>📁 OpenMontage</h1>
  <span class="path" id="curpath">/</span>
</header>
<div class="container">
  <div class="toolbar">
    <button onclick="nav('..')">⬆ 上级目录</button>
    <button onclick="showNewDir()">📂 新建目录</button>
    <label class="btn" id="upload-btn">📤 上传文件</label>
    <input type="file" id="upload-input" multiple>
    <button onclick="location.reload()">🔄 刷新</button>
    <span style="flex:1;min-width:0"></span>
    <span id="file-count" style="color:#484f58;font-size:12px;align-self:center"></span>
  </div>
  <table>
    <thead><tr><th class="icon"></th><th class="name">名称</th><th class="size">大小</th><th class="date">修改时间</th><th class="actions">操作</th></tr></thead>
    <tbody id="filelist"></tbody>
  </table>
  <div class="empty" id="empty">此目录为空</div>
</div>
<div id="progress"><div id="pgtxt">上传中...</div><div class="bar"><div class="fill" id="pgfill"></div></div></div>
<div class="modal-overlay" id="modal-overlay">
  <div class="modal">
    <h3 id="modal-title">操作</h3>
    <input id="modal-input" placeholder="输入名称">
    <div class="btns">
      <button class="cancel" onclick="closeModal()">取消</button>
      <button class="primary" id="modal-confirm">确认</button>
    </div>
  </div>
</div>
<footer>OpenMontage File Manager — serving <code id="footer-path"></code></footer>
<script>
let currentPath = '/';

function icon(name, isDir) {
  if (isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  if (['mp4','webm','mov','avi','mkv'].includes(ext)) return '🎬';
  if (['mp3','wav','ogg','flac','m4a'].includes(ext)) return '🎵';
  if (['jpg','jpeg','png','gif','svg','webp','ico'].includes(ext)) return '🖼';
  if (['json','yaml','yml','xml','toml'].includes(ext)) return '⚙';
  if (['py','js','ts','jsx','tsx','html','css','go','rs','c','cpp','h'].includes(ext)) return '📄';
  if (['zip','tar','gz','rar','7z'].includes(ext)) return '🗜';
  return '📄';
}

function sizeStr(bytes) {
  if (bytes === null || bytes === undefined) return '-';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function dateStr(ts) {
  if (!ts) return '-';
  const d = new Date(ts * 1000);
  return d.toLocaleString('zh-CN');
}

async function api(method, path, body) {
  const opts = { method };
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const r = await fetch('/api' + path, opts);
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(txt || r.statusText);
  }
  return r.headers.get('content-type')?.includes('json') ? r.json() : r.text();
}

async function load(dir) {
  currentPath = dir || '/';
  document.getElementById('curpath').textContent = currentPath;
  try {
    const entries = await api('GET', '?path=' + encodeURIComponent(currentPath));
    const tbody = document.getElementById('filelist');
    tbody.innerHTML = '';
    document.getElementById('empty').style.display = entries.length ? 'none' : 'block';
    document.getElementById('file-count').textContent = entries.length + ' 项';
    for (const e of entries) {
      const tr = document.createElement('tr');
      tr.className = e.is_dir ? 'dir' : '';
      const iconChar = icon(e.name, e.is_dir);
      const href = e.is_dir ? `javascript:nav('${e.name.replace(/'/g,"\\'")}')` : `/api/download?path=${encodeURIComponent(currentPath + e.name)}`;
      tr.innerHTML = `
        <td class="icon">${iconChar}</td>
        <td class="name"><a href="${href}" ${e.is_dir ? '' : 'target="_blank"'} title="${escHtml(e.name)}">${escHtml(e.name)}</a></td>
        <td class="size">${e.is_dir ? '-' : sizeStr(e.size)}</td>
        <td class="date">${dateStr(e.mtime)}</td>
        <td class="actions">
          <button onclick="rename('${e.name.replace(/'/g,"\\'")}', ${e.is_dir})">✏️</button>
          <button class="del" onclick="del('${e.name.replace(/'/g,"\\'")}', ${e.is_dir})">🗑</button>
        </td>`;
      tbody.appendChild(tr);
    }
  } catch (err) {
    alert('加载失败: ' + err.message);
  }
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function nav(name) {
  let p = currentPath;
  if (name === '..') {
    p = p.replace(/\/+$/, '');
    const i = p.lastIndexOf('/');
    p = i > 0 ? p.slice(0, i + 1) : '/';
  } else {
    p = (p + name).replace(/\/+/g, '/');
    if (!p.endsWith('/')) p += '/';
  }
  load(p);
}

async function del(name, isDir) {
  const label = (isDir ? '目录' : '文件') + ' "' + name + '"';
  if (!confirm('确定删除' + label + '？')) return;
  try {
    await api('DELETE', '?path=' + encodeURIComponent(currentPath + name));
    load(currentPath);
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

let renameTarget = null;
function rename(name, isDir) {
  renameTarget = { name, isDir, path: currentPath + name };
  document.getElementById('modal-title').textContent = '重命名 ' + (isDir ? '目录' : '文件');
  document.getElementById('modal-input').value = name;
  document.getElementById('modal-confirm').onclick = doRename;
  document.getElementById('modal-overlay').classList.add('active');
  document.getElementById('modal-input').focus();
  document.getElementById('modal-input').select();
}

async function doRename() {
  const newName = document.getElementById('modal-input').value.trim();
  if (!newName || newName === renameTarget.name) { closeModal(); return; }
  try {
    await api('PUT', '', { from: currentPath + renameTarget.name, to: currentPath + newName });
    closeModal();
    load(currentPath);
  } catch (err) {
    alert('重命名失败: ' + err.message);
  }
}

function showNewDir() {
  renameTarget = null;
  document.getElementById('modal-title').textContent = '新建目录';
  document.getElementById('modal-input').value = '';
  document.getElementById('modal-confirm').onclick = doNewDir;
  document.getElementById('modal-overlay').classList.add('active');
  document.getElementById('modal-input').focus();
}

async function doNewDir() {
  const name = document.getElementById('modal-input').value.trim();
  if (!name) { closeModal(); return; }
  try {
    await api('POST', '', { path: currentPath + name });
    closeModal();
    load(currentPath);
  } catch (err) {
    alert('创建失败: ' + err.message);
  }
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

// upload
document.getElementById('upload-input').addEventListener('change', async function() {
  const files = this.files;
  if (!files.length) return;
  const total = files.length;
  document.getElementById('progress').style.display = 'block';
  for (let i = 0; i < total; i++) {
    const f = files[i];
    document.getElementById('pgtxt').textContent = `上传中 (${i+1}/${total}): ${f.name}`;
    document.getElementById('pgfill').style.width = '0%';
    try {
      await uploadFile(f);
    } catch (err) {
      alert('上传失败 ' + f.name + ': ' + err.message);
    }
    document.getElementById('pgfill').style.width = '100%';
  }
  setTimeout(() => { document.getElementById('progress').style.display = 'none'; }, 1500);
  this.value = '';
  load(currentPath);
});

async function uploadFile(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', currentPath);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        document.getElementById('pgfill').style.width = (e.loaded / e.total * 100) + '%';
      }
    };
    xhr.onload = () => xhr.status === 200 ? resolve() : reject(new Error(xhr.responseText || xhr.statusText));
    xhr.onerror = () => reject(new Error('网络错误'));
    xhr.open('POST', '/api/upload', true);
    xhr.send(formData);
  });
}

// keyboard
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
  if (e.key === 'Enter' && document.getElementById('modal-overlay').classList.contains('active')) {
    document.getElementById('modal-confirm').click();
  }
});

load('/');
document.getElementById('footer-path').textContent = window.location.origin;
</script>
</body>
</html>"""


class FileManagerHandler(SimpleHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, status=400):
        self._send_json({"error": msg}, status)

    def _resolve(self, path):
        p = urllib.parse.unquote(path)
        p = os.path.normpath(os.path.join(ROOT, p.lstrip("/")))
        if not p.startswith(ROOT):
            return None  # prevent path traversal
        return p

    def _list_dir(self, rel_path):
        abs_path = self._resolve(rel_path)
        if not abs_path or not os.path.isdir(abs_path):
            self._send_error("Directory not found", 404)
            return
        entries = []
        try:
            for name in sorted(os.listdir(abs_path)):
                if name.startswith("."):
                    continue
                full = os.path.join(abs_path, name)
                st = os.stat(full)
                entries.append({
                    "name": name,
                    "is_dir": os.path.isdir(full),
                    "size": st.st_size if os.path.isfile(full) else None,
                    "mtime": int(st.st_mtime),
                })
        except PermissionError:
            self._send_error("Permission denied", 403)
            return
        self._send_json(entries)

    def _delete(self, rel_path):
        abs_path = self._resolve(rel_path)
        if not abs_path or not os.path.exists(abs_path):
            self._send_error("Not found", 404)
            return
        try:
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            self._send_json({"ok": True})
        except OSError as e:
            self._send_error(str(e), 500)

    def _rename(self, data):
        from_path = self._resolve(data.get("from", ""))
        to_path = self._resolve(data.get("to", ""))
        if not from_path or not to_path:
            self._send_error("Invalid paths", 400)
            return
        try:
            os.rename(from_path, to_path)
            self._send_json({"ok": True})
        except OSError as e:
            self._send_error(str(e), 500)

    def _mkdir(self, data):
        abs_path = self._resolve(data.get("path", ""))
        if not abs_path:
            self._send_error("Invalid path", 400)
            return
        try:
            os.makedirs(abs_path, exist_ok=True)
            self._send_json({"ok": True})
        except OSError as e:
            self._send_error(str(e), 500)

    def _upload(self):
        path = self.form.get("path", "/")
        if isinstance(path, bytes):
            path = path.decode()
        file_item = self.form.get("file")
        if not file_item:
            self._send_error("No file", 400)
            return
        filename = file_item.filename
        abs_path = self._resolve(os.path.join(path, filename))
        if not abs_path:
            self._send_error("Invalid path", 400)
            return
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(file_item.value)
            self._send_json({"ok": True})
        except OSError as e:
            self._send_error(str(e), 500)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api":
            qs = urllib.parse.parse_qs(parsed.query)
            rel = qs.get("path", ["/"])[0]
            self._list_dir(rel)
        elif parsed.path == "/api/download":
            qs = urllib.parse.parse_qs(parsed.query)
            rel = qs.get("path", ["/"])[0]
            abs_path = self._resolve(rel)
            if abs_path and os.path.isfile(abs_path):
                self.send_file(abs_path)
            else:
                self._send_error("File not found", 404)
        elif parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML.encode())))
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            self.send_file(self._resolve(parsed.path) or "", from_static=True)

    def send_file(self, abs_path, from_static=False):
        if not abs_path or not os.path.exists(abs_path):
            if from_static:
                self._send_error("Not found", 404)
            else:
                super().do_GET()
            return
        if os.path.isdir(abs_path):
            if from_static:
                self._send_error("Forbidden", 403)
            else:
                super().do_GET()
            return
        ctype, _ = mimetypes.guess_type(abs_path)
        ctype = ctype or "application/octet-stream"
        try:
            fsize = os.path.getsize(abs_path)
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(fsize))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(abs_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        except (OSError, BrokenPipeError):
            pass

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        rel = qs.get("path", ["/"])[0]
        self._delete(rel)

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw)
        self._rename(data)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/upload":
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" in ctype:
                import cgi
                self.form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST"},
                )
                self._upload()
                return
        elif parsed.path == "/api":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw)
            self._mkdir(data)
            return
        self._send_error("Unsupported", 400)


def main():
    os.chdir(ROOT)
    server = HTTPServer(("0.0.0.0", PORT), FileManagerHandler)
    print(f"OpenMontage File Manager running at:")
    print(f"  http://0.0.0.0:{PORT}/")
    print(f"  Serving: {ROOT}")
    print(f"  Features: browse | download | upload | rename | delete | create dir")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
