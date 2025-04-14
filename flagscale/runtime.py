import os
import sys
import shutil
from git.repo import Repo
import argparse


def create_symlinks(src_dir, dst_dir):
    for root, dirs, files in os.walk(src_dir):
        for filename in files:
            src_file = os.path.join(root, filename)
            
            rel_path = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel_path)

            dst_file_dir = os.path.dirname(dst_file)
            if not os.path.exists(dst_file_dir):
                os.makedirs(dst_file_dir)

            if os.path.exists(dst_file):
                os.remove(dst_file)
            os.symlink(src_file, dst_file)

            print(f"Created symbolic link: {filename} -> {rel_path}")


def init_submodule(dst, submodule_name):
    if os.path.exists(dst) and len(os.listdir(dst)) > 0:
        print(f"Skipping {submodule_name} initialization, as it already exists.")
        return
    print(f"Initializing submodule {submodule_name}...")
    repo = Repo(os.path.dirname(os.path.dirname(__file__)))
    repo.submodule_update(init=True, recursive=True)
    print(f"Initialized {submodule_name} submodule.")


def  patch_megatron():
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch or unpatch backend with symlinks.")
    parser.add_argument('--action', choices=["patch", "unpatch"], default="unpatch",
                        help="Action to perform: patch or unpatch (default: unpatch)")
    parser.add_argument('--backend', choices=["Megatron-LM", "vllm"], default="Megatron-LM",
                        help="Backend to process (default: Megatron-LM)")

    args = parser.parse_args()
    action = args.action
    backend = args.backend

    script_dir = os.path.dirname(os.path.realpath(__file__))
    # Megatron-LM
    if backend == "Megatron-LM":
        if action == "unpatch":
            src = os.path.join(script_dir, "train", backend)
            dst = os.path.join(script_dir, "..", "third_party", backend)
            init_submodule(dst, "Megatron-LM")
            create_symlinks(src, dst)
        elif action == "patch":
            patch_megatron()

    # # vllm will be supported in the future
    # elif backend == "vllm":
    # src = os.path.join(script_dir, "train", "vllm")
    # dst = os.path.join(script_dir, "..", "third_party", "vllm")
    # create_symlinks(src, dst)

    # Other backends will be supported in the future.
