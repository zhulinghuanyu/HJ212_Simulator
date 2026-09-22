# -*- coding: utf-8 -*-
"""一键打包脚本：python build.py  （默认打包当前平台）"""

import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=ROOT):
    print(">>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def main():
    # 1. 运行测试
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    subprocess.check_call([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                          cwd=ROOT, env=env)
    # 2. 清理
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    # 3. 打包
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "HJ212-Simulator.spec"])
    out = os.path.join(ROOT, "dist")
    print("\n打包完成，产物目录：", out)
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        size = os.path.getsize(p) / 1024 / 1024
        print("  %-24s %8.1f MB" % (f, size))


if __name__ == "__main__":
    main()
