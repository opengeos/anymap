from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
import shutil, os, subprocess
import platform

is_windows = platform.system() == "Windows"

class build_py(_build_py):
    def run(self):
        potree_repo = "https://github.com/potree/potree.git"
        potree_src = os.path.join("anymap", "static", "potree-src")
        potree_build = os.path.join(potree_src, "build", "potree")
        potree_dst = os.path.join("anymap", "static", "potree")

        if not os.path.exists(potree_src):
            print(f"Cloning Potree into {potree_src}...")
            subprocess.check_call(["git", "clone", "--depth", "1", potree_repo, potree_src])

        print("Installing npm dependencies...")
        subprocess.check_call(["npm", "install"], cwd=potree_src, shell=is_windows)

        print("Building Potree...")
        subprocess.check_call(["npm", "run", "build"], cwd=potree_src, shell=is_windows)

        print(f"Copying built Potree files to {potree_dst}...")
        if os.path.exists(potree_dst):
            shutil.rmtree(potree_dst)
        shutil.copytree(potree_build, potree_dst)

        # Proceed with normal build
        super().run()

setup(
    cmdclass={
        "build_py": build_py,
    }
)