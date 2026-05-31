"""
train_ner_model.py

Train NER model using the converted Label Studio data.
The NER model handles all entity extraction including:
- EVENT_NAME, DATE, VENUE, ORGANIZER, DEPARTMENT (core fields)
- CATEGORY, DOC_TYPE (document classification)

Note: ABSTRACT is handled separately, not part of NER training.

Usage:
    # Quick start with optimal defaults (25 epochs, clean checkpoints)
    python train_ner_model.py --clean --interactive
    
    # Quick training with auto-yes
    python train_ner_model.py --clean -y
    
    # Custom configuration
    python train_ner_model.py --epochs 30 --learning-rate 3e-5 --clean
    
    # Advanced options
    python train_ner_model.py --data training_data/ner_training_data.json \\
                              --output-dir ml_models/ner_model \\
                              --epochs 25 \\
                              --batch-size 8 \\
                              --learning-rate 3e-5 \\
                              --clean \\
                              --interactive
"""

import json
import argparse
import shutil
from pathlib import Path
from typing import List, Dict
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification
)
from sklearn.model_selection import train_test_split
import numpy as np

# -------------------------
# Constants
# -------------------------
# Focused NER labels - prioritizing key document fields
# ABSTRACT removed (handled separately via summarization or other method)
NER_LABELS = [
    'O',
    'B-EVENT_NAME', 'I-EVENT_NAME',      # Priority: High
    'B-DATE', 'I-DATE',
    'B-VENUE', 'I-VENUE',
    'B-ORGANIZER', 'I-ORGANIZER',
    'B-DEPARTMENT', 'I-DEPARTMENT',      # Priority: High
    'B-CATEGORY', 'I-CATEGORY',           # Priority: High (event type)
    'B-DOC_TYPE', 'I-DOC_TYPE'            # Priority: High
]

DEFAULT_MODEL = 'bert-base-uncased'


# -------------------------
# Focal Loss + Dice Loss
# -------------------------
class FocalLoss(nn.Module):
    """
    Focal Loss (Lin et al., 2017) for token classification.
    Down-weights easy examples and focuses training on hard entity boundaries.
    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
    """
    def __init__(self, alpha: float = 1.0, gamma: float = 2.0, ignore_index: int = -100):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.ignore_index = ignore_index

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # logits: (batch, seq_len, num_classes)  targets: (batch, seq_len)
        num_classes = logits.size(-1)
        logits_flat = logits.view(-1, num_classes)          # (N, C)
        targets_flat = targets.view(-1)                      # (N,)

        # Mask out ignored tokens
        mask = targets_flat != self.ignore_index
        logits_flat = logits_flat[mask]
        targets_flat = targets_flat[mask]

        if targets_flat.numel() == 0:
            return torch.tensor(0.0, device=logits.device, requires_grad=True)

        # Use cross_entropy with reduction='none' (avoids one_hot on CUDA)
        ce_loss = F.cross_entropy(logits_flat, targets_flat, reduction='none')  # (N,)
        probs = F.softmax(logits_flat.detach(), dim=-1)
        p_t = probs.gather(1, targets_flat.unsqueeze(1)).squeeze(1)  # (N,)

        focal_weight = self.alpha * (1.0 - p_t) ** self.gamma
        loss = focal_weight * ce_loss

        return loss.mean()


class DiceLoss(nn.Module):
    """
    Dice Loss for token classification.
    Directly optimises an F1-like overlap metric, effective for
    class-imbalanced sequence labelling (most tokens are 'O').
    DL = 1 - (2 * sum(p * y) + smooth) / (sum(p) + sum(y) + smooth)
    """
    def __init__(self, smooth: float = 1.0, ignore_index: int = -100):
        super().__init__()
        self.smooth = smooth
        self.ignore_index = ignore_index

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        num_classes = logits.size(-1)
        logits_flat = logits.view(-1, num_classes)
        targets_flat = targets.view(-1)

        mask = targets_flat != self.ignore_index
        logits_flat = logits_flat[mask]
        targets_flat = targets_flat[mask]

        if targets_flat.numel() == 0:
            return torch.tensor(0.0, device=logits.device, requires_grad=True)

        probs = F.softmax(logits_flat, dim=-1)                          # (N, C)
        # Build one-hot on CPU then move to device (avoids CUDA one_hot issues)
        targets_one_hot = torch.zeros_like(probs)
        targets_one_hot.scatter_(1, targets_flat.unsqueeze(1), 1.0)     # (N, C)

        intersection = (probs * targets_one_hot).sum(dim=0)             # (C,)
        cardinality = probs.sum(dim=0) + targets_one_hot.sum(dim=0)     # (C,)

        dice_per_class = (2.0 * intersection + self.smooth) / (cardinality + self.smooth)
        return 1.0 - dice_per_class.mean()


class FocalDiceLoss(nn.Module):
    """
    Combined Focal Loss + Dice Loss.
    L = lambda_focal * FL + lambda_dice * DL
    Default weighting: 0.5 each (equal contribution).
    """
    def __init__(self, alpha: float = 1.0, gamma: float = 2.0,
                 smooth: float = 1.0, ignore_index: int = -100,
                 lambda_focal: float = 0.5, lambda_dice: float = 0.5):
        super().__init__()
        self.focal = FocalLoss(alpha=alpha, gamma=gamma, ignore_index=ignore_index)
        self.dice = DiceLoss(smooth=smooth, ignore_index=ignore_index)
        self.lambda_focal = lambda_focal
        self.lambda_dice = lambda_dice

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.lambda_focal * self.focal(logits, targets) + \
               self.lambda_dice * self.dice(logits, targets)


# -------------------------
# Custom Trainer
# -------------------------
class NERTrainer(Trainer):
    """
    Custom Trainer that replaces default cross-entropy with
    combined Focal Loss + Dice Loss for NER token classification.
    """
    def __init__(self, *args, custom_loss_fn=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_loss_fn = custom_loss_fn or FocalDiceLoss()

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop('labels')
        outputs = model(**inputs)
        logits = outputs.logits   # (batch, seq_len, num_labels)
        loss = self.custom_loss_fn(logits, labels)
        return (loss, outputs) if return_outputs else loss


# -------------------------
# Checkpoint Cleaning
# -------------------------
def clean_checkpoints(model_dir: Path) -> int:
    """Remove old checkpoint directories"""
    if not model_dir.exists():
        return 0
    
    checkpoints_removed = 0
    for checkpoint in model_dir.glob('checkpoint-*'):
        if checkpoint.is_dir():
            print(f"   Removing: {checkpoint.name}")
            shutil.rmtree(checkpoint)
            checkpoints_removed += 1
    
    return checkpoints_removed


def show_training_estimates(num_examples: int, epochs: int, batch_size: int):
    """Display training time estimates"""
    steps_per_epoch = num_examples / batch_size
    total_steps = steps_per_epoch * epochs
    
    print(f"\n📊 Training Statistics:")
    print(f"   • Training examples: {num_examples}")
    print(f"   • Steps per epoch: {steps_per_epoch:.0f}")
    print(f"   • Total training steps: {total_steps:.0f}")
    print(f"   • Estimated time: ~{total_steps * 2 / 60:.0f}-{total_steps * 4 / 60:.0f} minutes")
    
    # Recommendations for small datasets
    if num_examples < 200:
        print(f"\n💡 Small Dataset Detected ({num_examples} examples):")
        if epochs < 20:
            print(f"   ⚠️  Consider training for 20-30 epochs instead of {epochs}")
        if total_steps < 300:
            print(f"   ⚠️  Total steps ({total_steps:.0f}) is low. Aim for 400-600 steps.")


# -------------------------
# NER Dataset
# -------------------------
class NERDataset(Dataset):
    def __init__(self, data: List[Dict], tokenizer, label_to_id: Dict[str, int]):
        self.data = data
        self.tokenizer = tokenizer
        self.label_to_id = label_to_id
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        tokens = item['tokens']
        ner_tags = item['ner_tags']
        
        # Tokenize with word-level alignment
        encoding = self.tokenizer(
            tokens,
            is_split_into_words=True,
            padding='max_length',
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )
        
        # Align labels with subword tokens
        labels = []
        word_ids = encoding.word_ids(batch_index=0)
        previous_word_idx = None
        
        for word_idx in word_ids:
            if word_idx is None:
                labels.append(-100)  # Special tokens
            elif word_idx != previous_word_idx:
                labels.append(ner_tags[word_idx])
            else:
                # For subword tokens, use -100 (ignore)
                labels.append(-100)
            previous_word_idx = word_idx
        
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(labels, dtype=torch.long)
        }


# -------------------------
# Helper Functions
# -------------------------
def load_json_data(filepath: str) -> List[Dict]:
    """Load training data from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_datasets(data: List[Dict], tokenizer, label_to_id: Dict[str, int], test_size: float = 0.2):
    """Split data and create train/validation datasets"""
    if len(data) < 10:
        print("⚠️  WARNING: Very small dataset. Using 90/10 split.")
        test_size = 0.1
    
    train_data, val_data = train_test_split(data, test_size=test_size, random_state=42)
    
    train_dataset = NERDataset(train_data, tokenizer, label_to_id)
    val_dataset = NERDataset(val_data, tokenizer, label_to_id)
    
    return train_dataset, val_dataset


def compute_metrics(pred):
    """Compute metrics for NER evaluation"""
    predictions, labels = pred
    predictions = np.argmax(predictions, axis=2)
    
    # Remove ignored index (special tokens)
    true_predictions = []
    true_labels = []
    
    for prediction, label in zip(predictions, labels):
        for pred_id, label_id in zip(prediction, label):
            if label_id != -100:
                true_predictions.append(pred_id)
                true_labels.append(label_id)
    
    # Calculate accuracy
    accuracy = sum(p == l for p, l in zip(true_predictions, true_labels)) / len(true_labels)
    
    return {'accuracy': accuracy}


# -------------------------
# Training Function
# -------------------------
def train_ner_model(
    train_data: List[Dict],
    output_dir: str,
    base_model: str = DEFAULT_MODEL,
    epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 2e-5
):
    """Train NER model"""
    print("\n" + "=" * 70)
    print("Training NER Model")
    print("=" * 70)
    
    # Create label mapping
    label_to_id = {label: idx for idx, label in enumerate(NER_LABELS)}
    id_to_label = {idx: label for label, idx in label_to_id.items()}
    
    # Load tokenizer and model
    print(f"\n📥 Loading base model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(NER_LABELS),
        id2label=id_to_label,
        label2id=label_to_id
    )
    
    # Create datasets
    print(f"\n📊 Splitting data: {len(train_data)} examples")
    train_dataset, val_dataset = create_datasets(train_data, tokenizer, label_to_id)
    print(f"   - Training: {len(train_dataset)} examples")
    print(f"   - Validation: {len(val_dataset)} examples")
    
    # Training arguments
    # Note: Use eval_strategy for transformers >= 4.19, evaluation_strategy for older versions
    import transformers
    transformers_version = tuple(int(x) for x in transformers.__version__.split('.')[:2])
    
    training_args_dict = {
        'output_dir': output_dir,
        'learning_rate': learning_rate,
        'per_device_train_batch_size': batch_size,
        'per_device_eval_batch_size': batch_size,
        'num_train_epochs': epochs,
        'weight_decay': 0.01,
        'save_strategy': 'epoch',
        'save_total_limit': 2,
        'load_best_model_at_end': True,
        'metric_for_best_model': 'accuracy',
        'logging_steps': 10,
        'push_to_hub': False,
    }
    
    # Add version-specific parameters
    if transformers_version >= (4, 19):
        training_args_dict['eval_strategy'] = 'epoch'
        training_args_dict['report_to'] = 'none'
    else:
        training_args_dict['evaluation_strategy'] = 'epoch'
        training_args_dict['report_to'] = []
    
    training_args = TrainingArguments(**training_args_dict)
    
    # Data collator
    data_collator = DataCollatorForTokenClassification(tokenizer)
    
    # Loss function: Combined Focal Loss + Dice Loss
    loss_fn = FocalDiceLoss(
        alpha=1.0,           # Focal loss class-balance factor
        gamma=2.0,           # Focal loss focusing parameter
        smooth=1.0,          # Dice loss smoothing
        ignore_index=-100,   # Ignore special tokens
        lambda_focal=0.5,    # Weight for Focal Loss component
        lambda_dice=0.5,     # Weight for Dice Loss component
    )
    print(f"\n📐 Loss function: Focal Loss (γ=2.0) + Dice Loss (smooth=1.0)")
    
    # Trainer (custom NERTrainer with Focal+Dice loss)
    trainer = NERTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        custom_loss_fn=loss_fn,
    )
    
    # Train
    print(f"\n🚀 Starting training for {epochs} epochs...")
    trainer.train()
    
    # Evaluate
    print("\n📊 Evaluating on validation set...")
    eval_results = trainer.evaluate()
    print(f"   Validation Accuracy: {eval_results['eval_accuracy']:.4f}")
    
    # Save
    print(f"\n💾 Saving model to: {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    # Save label mapping
    label_map_path = Path(output_dir) / 'label_map.json'
    with open(label_map_path, 'w') as f:
        json.dump({'label_to_id': label_to_id, 'id_to_label': id_to_label}, f, indent=2)
    
    print("✅ NER model training complete!")
    return eval_results


# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description='Train NER model')
    parser.add_argument('--data', type=str, default='training_data/ner_training_data.json',
                       help='Path to NER training data JSON')
    parser.add_argument('--output-dir', type=str, default='backend/ml_models/ner_model',
                       help='Directory for saving trained model')
    parser.add_argument('--base-model', type=str, default=DEFAULT_MODEL,
                       help='Base model for NER')
    parser.add_argument('--epochs', type=int, default=25,
                       help='Number of training epochs (default: 25 for small datasets)')
    parser.add_argument('--batch-size', type=int, default=8,
                       help='Batch size for training')
    parser.add_argument('--learning-rate', type=float, default=3e-5,
                       help='Learning rate (default: 3e-5 for better convergence)')
    parser.add_argument('--clean', action='store_true',
                       help='Clean old checkpoints before training')
    parser.add_argument('--interactive', action='store_true',
                       help='Show recommendations and ask for confirmation')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='Skip all confirmations (auto-yes)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("NER Model Training Pipeline")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"   Data: {args.data}")
    print(f"   Output Directory: {output_dir}")
    print(f"   Base Model: {args.base_model}")
    print(f"   Epochs: {args.epochs}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Learning Rate: {args.learning_rate}")
    if args.clean:
        print(f"   Clean Mode: ✅ Will remove old checkpoints")
    
    # Load data first to show estimates
    try:
        train_data = load_json_data(args.data)
        print(f"\n✅ Loaded {len(train_data)} training examples")
        
        # Show training estimates
        show_training_estimates(len(train_data), args.epochs, args.batch_size)
        
        # Interactive confirmation
        if args.interactive and not args.yes:
            print("\n" + "=" * 70)
            response = input("Continue with training? [Y/n]: ").strip().lower()
            if response and response != 'y':
                print("\n❌ Training cancelled")
                return
        
        # Clean checkpoints if requested
        if args.clean:
            print("\n" + "=" * 70)
            print("Cleaning old checkpoints...")
            print("=" * 70)
            removed = clean_checkpoints(output_dir)
            if removed > 0:
                print(f"✅ Removed {removed} checkpoint(s)")
            else:
                print("✅ No checkpoints to remove")
        
        # Train model
        print("\n" + "=" * 70)
        print("Starting Training...")
        print("=" * 70)
        
        eval_results = train_ner_model(
            train_data=train_data,
            output_dir=str(output_dir),
            base_model=args.base_model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate
        )
        
        print("\n" + "=" * 70)
        print("✅ TRAINING COMPLETE!")
        print("=" * 70)
        print(f"\nModel saved to: {output_dir}")
        if eval_results and 'eval_accuracy' in eval_results:
            print(f"\nValidation Accuracy: {eval_results['eval_accuracy']:.2%}")
        print("\nNext steps:")
        print("1. Test the model:")
        print(f"   python test_ner_agent.py")
        print("2. Update your .env file (if needed):")
        print(f"   NER_MODEL_DIR={output_dir}")
        print("3. Restart your application to use the new model")
        print("\nQuick test command:")
        print(f"   python test_ner_agent.py --ner-model {output_dir}")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()