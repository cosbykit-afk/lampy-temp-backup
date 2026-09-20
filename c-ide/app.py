"""Lampy C IDE — a Python (Flask) based IDE for C with GCC.

Editor + Compile & Run + workspace file save/load. No CDN dependencies;
plain textarea + vanilla JS so it works behind a flaky proxy.
DRAFT 2026-09-19.
"""
import os
import shutil
import subprocess
import tempfile

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(BASE, "workspace")
os.makedirs(WORKSPACE, exist_ok=True)

MAX_SOURCE = 200_000      # 200 KB per file
TIME_LIMIT = 10           # seconds, compile and run each


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=TIME_LIMIT, **kw)


def safe_name(name):
    clean = "".join(c for c in (name or "prog") if c.isalnum() or c in "_-")
    return clean or "prog"


def safe_path(name):
    # confine to WORKSPACE: no slashes, no dotfiles
    clean = safe_name(name)
    if clean != name or name.startswith("."):
        return None
    return os.path.join(WORKSPACE, clean + ".c")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/files")
def list_files():
    files = sorted(f[:-2] for f in os.listdir(WORKSPACE)
                   if f.endswith(".c") and os.path.isfile(os.path.join(WORKSPACE, f)))
    return jsonify(files=files)


@app.route("/api/files/<name>")
def load_file(name):
    path = safe_path(name)
    if not path or not os.path.isfile(path):
        return jsonify(ok=False, error="not found"), 404
    with open(path) as f:
        return jsonify(ok=True, name=name, source=f.read())


@app.route("/api/files/<name>", methods=["PUT"])
def save_file(name):
    path = safe_path(name)
    if not path:
        return jsonify(ok=False, error="bad name"), 400
    source = (request.get_json(force=True) or {}).get("source", "")
    if len(source) > MAX_SOURCE:
        return jsonify(ok=False, error="source too large"), 400
    with open(path, "w") as f:
        f.write(source)
    return jsonify(ok=True, name=name)


@app.route("/api/compile", methods=["POST"])
def compile_c():
    data = request.get_json(force=True) or {}
    name = safe_name(data.get("name"))
    source = data.get("source", "")
    if len(source) > MAX_SOURCE:
        return jsonify(ok=False, error="source too large"), 400
    flags = (data.get("flags") or "-Wall -Wextra -O2").split()

    tmp = tempfile.mkdtemp(prefix="cide_")
    try:
        src = os.path.join(tmp, name + ".c")
        exe = os.path.join(tmp, name)
        with open(src, "w") as f:
            f.write(source)
        cc = run(["gcc"] + flags + [src, "-o", exe])
        if cc.returncode != 0:
            return jsonify(ok=False, stage="compile",
                           stdout=cc.stdout, stderr=cc.stderr,
                           exit_code=cc.returncode)
        try:
            prog = run([exe], input=data.get("stdin", ""))
        except subprocess.TimeoutExpired:
            return jsonify(ok=False, stage="timeout",
                           error="program exceeded time limit"), 200
        return jsonify(ok=True, stage="run",
                       compile_stdout=cc.stdout, compile_stderr=cc.stderr,
                       stdout=prog.stdout, stderr=prog.stderr,
                       exit_code=prog.returncode)
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, stage="timeout",
                       error="compile exceeded time limit"), 200
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8090)
