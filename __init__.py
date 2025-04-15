import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flagscale.runtime import unpatch
# Initialize Megatron-LM and create megatron_lm symlinks
src = os.path.join(os.path.dirname(__file__), "flagscale", "train", "Megatron-LM")
dst = os.path.join(os.path.dirname(__file__), "third_party", "Megatron-LM")
unpatch(src, dst, "third_party/Megatron-LM")



# Initialize vllm and create vllm symlinks
# src = os.path.join(os.path.dirname(__file__), "flagscale", "inference", "vllm")
# dst = os.path.join(os.path.dirname(__file__), "third_party", "vllm")
# unpatch(src, dst, "vllm")
