"""Smoke demo: move, rewrite, read, list, remove — all through generated scripts."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lampy_control import FileOps

ops = FileOps()
base = os.path.expanduser("~/workspace/forum-stack/control-plane/demo_area")

r = ops.mkdir(base); assert r.ok, r.stderr
r = ops.rewrite(os.path.join(base, "hello.txt"), "hello lampy\nsecond line\n")
assert r.ok, r.stderr
print("script:", r.script_path)

r = ops.read_file(os.path.join(base, "hello.txt")); assert r.ok, r.stderr
print("read back:", repr(r.stdout))

r = ops.move(os.path.join(base, "hello.txt"), os.path.join(base, "sub", "hello2.txt"))
assert r.ok, r.stderr
r = ops.list_dir(os.path.join(base, "sub")); assert r.ok, r.stderr
print(r.stdout.strip())

# outside-root must be refused before any script is written
try:
    ops.rewrite("/etc/lampy_should_not_exist", "x")
    raise SystemExit("FAIL: outside root was not refused")
except Exception as e:
    print("outside-root refused:", type(e).__name__)

r = ops.remove(os.path.join(base, "sub", "hello2.txt")); assert r.ok, r.stderr
print("removed -> trash; demo OK")
