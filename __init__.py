import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flagscale.runtime import create_symlinks, init_submodule
# Initialize Megatron-LM and create megatron_lm symlinks
src = os.path.join(os.path.dirname(__file__), "flagscale", "train", "Megatron-LM")
dst = os.path.join(os.path.dirname(__file__), "third_party", "Megatron-LM")
init_submodule(dst, "Megatron-LM")
raise ValueError()
create_symlinks(src, dst)


# Initialize vllm and create vllm symlinks
# src = os.path.join(os.path.dirname(__file__), "flagscale", "inference", "vllm")
# dst = os.path.join(os.path.dirname(__file__), "third_party", "vllm")
# init_submodule(dst, "vllm")
# create_symlinks(src, dst)
