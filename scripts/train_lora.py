#!/usr/bin/env python3
"""
LoRA Fine-Tuning Script for code4u.ai

Usage:
    python scripts/train_lora.py --dataset training_data/dataset.jsonl --output ./lora-output

Requirements:
    pip install transformers peft datasets bitsandbytes accelerate
"""
import argparse
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))


def main():
    parser = argparse.ArgumentParser(description="Train LoRA adapter for code4u.ai")
    parser.add_argument("--dataset", required=True, help="Path to training dataset (JSONL)")
    parser.add_argument("--output", default="./lora-output", help="Output directory")
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-32B", help="Base model")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--export-vllm", action="store_true", help="Export for vLLM serving")
    args = parser.parse_args()

    from code4u.ai_engine.training.trainer import LoRATrainer, TrainingConfig
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  code4u.ai LoRA Training                     ║
╠══════════════════════════════════════════════════════════════╣
║  Model:     {args.model:<47} ║
║  Dataset:   {args.dataset:<47} ║
║  Output:    {args.output:<47} ║
║  Epochs:    {args.epochs:<47} ║
║  LoRA Rank: {args.lora_r:<47} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    config = TrainingConfig(
        base_model=args.model,
        output_dir=args.output,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
    )
    
    trainer = LoRATrainer(config)
    adapter_path = trainer.train(args.dataset)
    
    print(f"\n✅ Training complete! Adapter saved to: {adapter_path}")
    
    if args.export_vllm:
        vllm_path = trainer.export_for_vllm(adapter_path, "code4u")
        print(f"✅ Exported for vLLM: {vllm_path}")
        print(f"""
To use with vLLM:
    python -m vllm.entrypoints.openai.api_server \\
        --model {args.model} \\
        --enable-lora \\
        --lora-modules code4u={vllm_path}
        """)


if __name__ == "__main__":
    main()

