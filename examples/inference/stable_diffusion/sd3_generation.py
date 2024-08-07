import argparse

from diffusers import PixArtAlphaPipeline, StableDiffusion3Pipeline
from torch import bfloat16, float16, float32

import colossalai
from colossalai.cluster import DistCoordinator
from colossalai.inference.config import DiffusionGenerationConfig, InferenceConfig
from colossalai.inference.core.engine import InferenceEngine
from colossalai.inference.modeling.policy.pixart_alpha import PixArtAlphaInferPolicy
from colossalai.inference.modeling.policy.stablediffusion3 import StableDiffusion3InferPolicy

# For Stable Diffusion 3, we'll use the following configuration
MODEL_CLS = [StableDiffusion3Pipeline, PixArtAlphaPipeline][0]
POLICY_CLS = [StableDiffusion3InferPolicy, PixArtAlphaInferPolicy][0]

TORCH_DTYPE_MAP = {
    "fp16": float16,
    "fp32": float32,
    "bf16": bfloat16,
}


def infer(args):
    # ==============================
    # Launch colossalai, setup distributed environment
    # ==============================
    colossalai.launch_from_torch()
    coordinator = DistCoordinator()

    # ==============================
    # Load model and tokenizer
    # ==============================
    model_path_or_name = args.model
    model = MODEL_CLS.from_pretrained(model_path_or_name, torch_dtype=TORCH_DTYPE_MAP.get(args.dtype, None))

    # ==============================
    # Initialize InferenceEngine
    # ==============================
    coordinator.print_on_master(f"Initializing Inference Engine...")
    inference_config = InferenceConfig(
        dtype=args.dtype,
        max_batch_size=args.max_batch_size,
        tp_size=args.tp_size,
        use_cuda_kernel=args.use_cuda_kernel,
    )
    engine = InferenceEngine(model, inference_config=inference_config, model_policy=POLICY_CLS(), verbose=True)

    # ==============================
    # Generation
    # ==============================
    coordinator.print_on_master(f"Generating...")
    out = engine.generate(prompts=[args.prompt], generation_config=DiffusionGenerationConfig())[0]
    out.save("cat.jpg")
    coordinator.print_on_master(out)


# colossalai run --nproc_per_node 1 examples/inference/stable_diffusion/sd3_generation.py -m MODEL_PATH
# colossalai run --nproc_per_node 1 examples/inference/stable_diffusion/sd3_generation.py -m "stabilityai/stable-diffusion-3-medium-diffusers" --tp_size 1


if __name__ == "__main__":
    # ==============================
    # Parse Arguments
    # ==============================
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", type=str, help="Path to the model or model name")
    parser.add_argument("-t", "--tp_size", type=int, default=1, help="Tensor Parallelism size")
    parser.add_argument("-p", "--prompt", type=str, default="A cat holding a sign that says hello world", help="Prompt")
    parser.add_argument("-b", "--max_batch_size", type=int, default=1, help="Max batch size")
    parser.add_argument("-d", "--dtype", type=str, default="fp16", help="Data type", choices=["fp16", "fp32", "bf16"])
    parser.add_argument("--use_cuda_kernel", action="store_true", help="Use CUDA kernel, use Triton by default")
    args = parser.parse_args()

    infer(args)
