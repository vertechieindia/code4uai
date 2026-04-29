from __future__ import annotations
"""LoRA fine-tuning trainer for code4u.ai.

Uses QLoRA (4-bit quantization + LoRA adapters) for efficient training.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger("training.trainer")


@dataclass
class TrainingConfig:
    """Configuration for LoRA fine-tuning."""
    # Model
    base_model: str = "Qwen/Qwen2.5-Coder-32B"
    
    # LoRA parameters
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] | None = None
    
    # Training parameters
    batch_size: int = 1
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    num_epochs: int = 3
    warmup_ratio: float = 0.1
    max_seq_length: int = 4096
    
    # Quantization
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "float16"
    
    # Output
    output_dir: str = "./lora-output"
    save_strategy: str = "epoch"
    logging_steps: int = 50
    
    def __post_init__(self):
        if self.target_modules is None:
            self.target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]


class LoRATrainer:
    """
    QLoRA trainer for code4u.ai.
    
    Training approach:
    - 4-bit quantization for memory efficiency
    - LoRA adapters for fast iteration
    - Supervised fine-tuning on refactoring examples
    """
    
    def __init__(self, config: TrainingConfig | None = None):
        self.config = config or TrainingConfig()
        self.logger = logger
    
    def train(self, dataset_path: str) -> str:
        """
        Run LoRA fine-tuning.
        
        Returns path to trained adapter.
        """
        self.logger.info(
            "starting_training",
            model=self.config.base_model,
            dataset=dataset_path
        )
        
        # Import here to avoid loading heavy libs until needed
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            DataCollatorForLanguageModeling,
        )
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from datasets import load_dataset
        import torch
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            self.config.base_model,
            trust_remote_code=True
        )
        tokenizer.pad_token = tokenizer.eos_token
        
        # Load model with quantization
        model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            load_in_4bit=self.config.load_in_4bit,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Prepare for k-bit training
        model = prepare_model_for_kbit_training(model)
        
        # Configure LoRA
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM"
        )
        
        model = get_peft_model(model, lora_config)
        
        self.logger.info(
            "model_loaded",
            trainable_params=model.print_trainable_parameters()
        )
        
        # Load and preprocess dataset
        dataset = load_dataset("json", data_files=dataset_path)
        
        def tokenize_example(batch):
            # Build prompt from example
            prompt = self._build_training_prompt(batch)
            return tokenizer(
                prompt,
                truncation=True,
                max_length=self.config.max_seq_length,
                padding="max_length"
            )
        
        tokenized_dataset = dataset["train"].map(
            tokenize_example,
            remove_columns=dataset["train"].column_names
        )
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            per_device_train_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            num_train_epochs=self.config.num_epochs,
            warmup_ratio=self.config.warmup_ratio,
            fp16=True,
            logging_steps=self.config.logging_steps,
            save_strategy=self.config.save_strategy,
            optim="paged_adamw_32bit",
            gradient_checkpointing=True,
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False
        )
        
        # Create trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )
        
        # Train
        self.logger.info("training_started")
        trainer.train()
        
        # Save adapter
        adapter_path = Path(self.config.output_dir) / "final_adapter"
        model.save_pretrained(str(adapter_path))
        tokenizer.save_pretrained(str(adapter_path))
        
        self.logger.info("training_complete", adapter_path=str(adapter_path))
        return str(adapter_path)
    
    def _build_training_prompt(self, example: Dict[str, Any]) -> str:
        """Build training prompt from example."""
        context = example.get("context", {})
        constraints = context.get("constraints", [])
        components = context.get("affected_components", [])
        
        constraints_str = "\n".join(f"- {c}" for c in constraints) or "- None"
        components_str = "\n".join(f"- {c}" for c in components) or "- None"
        
        input_code = example.get("input_code", {})
        expected = example.get("expected_output", {})
        
        return f"""SYSTEM:
You are a deterministic code refactoring engine for code4u.ai.
Output ONLY unified diff format. No explanations.

INSTRUCTION:
{example.get('instruction', '')}

CONTEXT:
- Language: {context.get('language', 'unknown')}
- Frameworks: {', '.join(context.get('frameworks', []))}

CONSTRAINTS:
{constraints_str}

AFFECTED COMPONENTS:
{components_str}

INPUT CODE:
```{context.get('language', '')}
{input_code.get('content', '')}
```

OUTPUT:
```diff
{expected.get('diff', '')}
```
---END---"""
    
    def export_for_vllm(self, adapter_path: str, output_name: str = "code4u") -> str:
        """
        Export adapter for vLLM serving.
        
        vLLM supports LoRA adapters via --lora-modules flag.
        """
        from pathlib import Path
        import shutil
        
        source = Path(adapter_path)
        vllm_dir = Path("./lora-adapters") / output_name
        vllm_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy adapter files
        for file in ["adapter_config.json", "adapter_model.safetensors"]:
            if (source / file).exists():
                shutil.copy(source / file, vllm_dir / file)
        
        self.logger.info("exported_for_vllm", path=str(vllm_dir))
        return str(vllm_dir)


def create_sample_dataset() -> None:
    """Create a sample training dataset for testing."""
    from code4u.ai_engine.training.dataset import (
        DatasetBuilder, TrainingExample, CodeContext, InputCode, ExpectedOutput, ExampleType
    )
    
    builder = DatasetBuilder()
    
    # Example 1: Simple rename
    builder.add_example(TrainingExample(
        instruction="Rename the variable 'email' to 'primaryEmail'",
        context=CodeContext(
            language="python",
            frameworks=["fastapi", "pydantic"],
            constraints=["Preserve validation", "Update all references"],
            affected_components=["UserSchema", "UserService"],
        ),
        input_code=InputCode(
            file_path="schemas/user.py",
            content="""from pydantic import BaseModel

class User(BaseModel):
    id: int
    email: str
    name: str
""",
        ),
        expected_output=ExpectedOutput(
            diff="""--- a/schemas/user.py
+++ b/schemas/user.py
@@ -3,5 +3,5 @@
 class User(BaseModel):
     id: int
-    email: str
+    primaryEmail: str
     name: str"""
        ),
        example_type=ExampleType.REFACTOR_DIFF,
        breaking_change=True,
    ))
    
    # Example 2: React component extraction
    builder.add_example(TrainingExample(
        instruction="Extract the button into a separate Button component",
        context=CodeContext(
            language="typescript",
            frameworks=["react"],
            constraints=["Preserve props", "Maintain styling"],
            affected_components=["UserProfile"],
        ),
        input_code=InputCode(
            file_path="components/UserProfile.tsx",
            content="""export function UserProfile({ user }) {
  return (
    <div className="profile">
      <h1>{user.name}</h1>
      <button onClick={() => alert('clicked')}>
        Click me
      </button>
    </div>
  );
}
""",
        ),
        expected_output=ExpectedOutput(
            diff="""--- a/components/UserProfile.tsx
+++ b/components/UserProfile.tsx
@@ -1,10 +1,15 @@
+function Button({ onClick, children }) {
+  return <button onClick={onClick}>{children}</button>;
+}
+
 export function UserProfile({ user }) {
   return (
     <div className="profile">
       <h1>{user.name}</h1>
-      <button onClick={() => alert('clicked')}>
+      <Button onClick={() => alert('clicked')}>
         Click me
-      </button>
+      </Button>
     </div>
   );
 }"""
        ),
        example_type=ExampleType.REFACTOR_DIFF,
    ))
    
    # Example 3: Rejection case
    builder.add_reject_example(
        instruction="Refactor this function",
        reason="No specific refactoring intent provided",
        input_code="def foo(): pass",
        language="python",
    )
    
    # Save dataset
    jsonl_path = builder.save_jsonl("sample_dataset.jsonl")
    stats = builder.get_stats()
    
    print(f"Created sample dataset at: {jsonl_path}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    create_sample_dataset()

