import os
import sys
import types
import importlib

import torch


def add_arguments(parser):
    group = parser.add_argument_group(title='Transformers loader')

    group.add_argument('--true-vocab-size', type=int, default=None,
                       help='original size of vocab, if specified will trim padding from embedding table.')
    group.add_argument('--vocab-file', type=str, default=None,
                       help='Path to the vocab file. If specified will use this to get vocab size and '
                       'trim padding from the embedding table.')
    group.add_argument('--megatron-path', type=str, default=None,
                       help='Base directory of deepspeed repository')

def _load_checkpoint(queue, args):
    try:
        import transformers
        major, minor, _ = map(int, transformers.__version__.split('.'))
        assert major >= 4 and minor >= 31
    except:
        raise ImportError("transformers version >= 4.31.0 ")

    # Search in directory above this.
    root_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     os.path.pardir))
    sys.path.append(os.path.join(root_path, "megatron"))

    if args.megatron_path is not None:
        sys.path.insert(0, args.megatron_path)

    try:
        from megatron.arguments import parse_args, validate_args
        from megatron.global_vars import set_global_variables
        from megatron.model import module
        from megatron.core import mpu
        from megatron import fused_kernels
        from megatron.core.tensor_parallel.random import (
                _CUDA_RNG_STATE_TRACKER, _DATA_PARALLEL_RNG_TRACKER_NAME, 
                _EXPERT_PARALLEL_RNG_TRACKER_NAME, _MODEL_PARALLEL_RNG_TRACKER_NAME
            )
    except ModuleNotFoundError:
        print("Unable to import Megatron, please specify the path to Megatron using --megatron-path. Exiting.")
        queue.put("exit")
        exit(1)

    try:
        args_plugin = importlib.import_module(args.model_type + ".args")
        ckpt_plugin = importlib.import_module(args.model_type + ".ckpt")
        model_plugin = importlib.import_module(args.model_type + ".model")
    except ModuleNotFoundError:
        raise ModuleNotFoundError("Please check model_type, args.py, ckpt.py or model.py")

    def queue_put(name, msg):
        print(f"sending {name}")
        msg["name"] = name
        queue.put(msg)

    # We want all arguments to come from us.
    sys.argv = [
        'script.py',
        '--no-masked-softmax-fusion',
        '--no-bias-gelu-fusion',
        '--no-bias-dropout-fusion',
        '--no-async-tensor-model-parallel-allreduce',
        '--use-cpu-initialization',
        '--micro-batch-size', '1',
        '--no-load-optim',
        '--no-load-rng',
        '--use-mcore-models',
        '--no-save-optim',
        '--no-save-rng',
        '--no-initialization',
        '--load', args.load_dir
    ]

    margs = parse_args()
    args_plugin.load_args_hf2mg(margs)
    margs.world_size = margs.tensor_model_parallel_size * margs.pipeline_model_parallel_size * margs.expert_model_parallel_size

    print("*"*20 + "validate loader arguments" + "*"*20)
    margs = validate_args(margs)

    def check_for_arg(arg_name, default=None):
        if getattr(margs, arg_name, None) is None:
            if default is not None:
                setattr(margs, arg_name, default)
            else:
                print(f"Checkpoint does not specify the argument {arg_name}. Exiting.")
                print(f"Arguments: {margs}")
                queue.put("exit")
                exit(1)

    check_for_arg('tensor_model_parallel_size')
    check_for_arg('pipeline_model_parallel_size')
    check_for_arg('expert_model_parallel_size')
    check_for_arg('num_layers')
    check_for_arg('hidden_size')
    check_for_arg('seq_length')
    check_for_arg('num_attention_heads')
    check_for_arg('max_position_embeddings')
    check_for_arg('position_embedding_type')
    check_for_arg('iteration')
    check_for_arg('params_dtype')
    check_for_arg('swiglu', False)
    check_for_arg('disable_bias_linear', not getattr(margs, "add_bias_linear", False))
    check_for_arg('add_qkv_bias', getattr(margs, "add_bias_linear_qkv", False))

    # Determine how to make our models.
    margs.model_type = model_plugin.model_type

    # Suppress warning about torch.distributed not being initialized.
    module.MegatronModule.embedding_warning_printed = True

    # fake distributed env
    assert margs.world_size == 1
    set_global_variables(margs, build_tokenizer=False)
    mpu.set_tensor_model_parallel_world_size(margs.tensor_model_parallel_size)
    mpu.set_pipeline_model_parallel_world_size(margs.pipeline_model_parallel_size)
    mpu.set_expert_model_parallel_world_size(margs.expert_model_parallel_size)
    mpu.set_tensor_model_parallel_rank(0)
    mpu.set_pipeline_model_parallel_rank(0)
    mpu.set_expert_model_parallel_rank(0)

    # fused kernel
    fused_kernels.load(margs)

    # random
    _CUDA_RNG_STATE_TRACKER.reset()
    torch.cuda.manual_seed(42)
    _CUDA_RNG_STATE_TRACKER.add(_DATA_PARALLEL_RNG_TRACKER_NAME, 43)
    _CUDA_RNG_STATE_TRACKER.add(_MODEL_PARALLEL_RNG_TRACKER_NAME, 44)
    _CUDA_RNG_STATE_TRACKER.add(_EXPERT_PARALLEL_RNG_TRACKER_NAME, 45)

    # Metadata.
    md = types.SimpleNamespace()
    md.model_type = args.model_type
    md.num_layers = margs.num_layers
    md.hidden_size = margs.hidden_size
    md.seq_length = margs.seq_length
    md.num_attention_heads = margs.num_attention_heads
    md.max_position_embeddings = margs.max_position_embeddings
    md.iteration = margs.iteration
    md.params_dtype = margs.params_dtype
    md.output_layer = margs.untie_embeddings_and_output_weights
    md.position_embedding_type = margs.position_embedding_type
    md.add_bias_linear = margs.add_bias_linear
    md.add_qkv_bias = margs.add_qkv_bias
    md.norm_has_bias = margs.norm_has_bias
    md.swiglu = margs.swiglu
    md.previous_num_experts = margs.num_experts
    md.previous_tensor_parallel_size = margs.tensor_model_parallel_size
    md.previous_pipeline_parallel_size = margs.pipeline_model_parallel_size
    md.previous_expert_parallel_size = margs.expert_model_parallel_size
    md.previous_virtual_pipeline_parallel_size = margs.virtual_pipeline_model_parallel_size
    md.true_vocab_size = args.true_vocab_size
    md.make_vocab_size_divisible_by = margs.make_vocab_size_divisible_by
    md.checkpoint_args = margs
    md.consumed_train_samples = margs.consumed_train_samples
    md.consumed_valid_samples = margs.consumed_valid_samples
    queue.put(md)

    # load ckpt
    model = ckpt_plugin.load_checkpoint_hf2mg(margs)

    # Send embeddings.
    message = dict()
    message["word embeddings"]= model.embedding.word_embeddings.weight.data
    if md.position_embedding_type == 'learned_absolute':
        message["position embeddings"] = model.embedding.position_embeddings.weight.data
    else:
        assert not hasattr(model.embedding, 'position_embeddings')
    queue_put("embeddings", message)

    # Send transformer layers
    for layer_id in range(margs.num_layers):
        message = dict()

        ckpt_plugin.get_attn_ckpt(message, [model], layer_id, margs)
        ckpt_plugin.get_mlp_ckpt(message, [model], layer_id, margs)

        queue_put(f"transformer layer {layer_id}", message)

    # Send final norm from tp_rank 0.
    message = {"weight": model.decoder.final_layernorm.weight.data}
    if md.norm_has_bias:
        message["bias"] = model.decoder.final_layernorm.bias.data
    queue_put("final norm", message)

    if md.output_layer:
        message = {"weight": model.output_layer.weight.data}
        queue_put("output layer", message)

    queue.put("done")


def load_checkpoint(queue, args):
    try:
        _load_checkpoint(queue, args)
    except:
        queue.put("exit")
        raise