import os
import sys
import shutil


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

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    patch_src = os.path.join(script_dir, "train", "Megatron-LM")
    megatron_lm_dst = os.path.join(script_dir, "..", "third_party", "Megatron-LM")
    create_symlinks(patch_src, megatron_lm_dst)
