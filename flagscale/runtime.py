import os
import sys
import shutil
from git.repo import Repo


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
    repo = Repo(os.path.dirname(__file__))
    repo.submodule_update(init=True, recursive=True)
    print(f"Initialized {submodule_name} submodule.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    # Megatron-LM
    src = os.path.join(script_dir, "train", "Megatron-LM")
    dst = os.path.join(script_dir, "..", "third_party", "Megatron-LM")
    create_symlinks(src, dst)

    # # vllm will be supported in the future.abs
    # src = os.path.join(script_dir, "train", "vllm")
    # dst = os.path.join(script_dir, "..", "third_party", "vllm")
    # create_symlinks(src, dst)
