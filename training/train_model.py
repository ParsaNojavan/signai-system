import os
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from tqdm import tqdm
import matplotlib.pyplot as plt

from model import SignLanguageBiLSTM

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "dataset" / "MP_Data"
ACTIONS_FILE = BASE_DIR / "dataset" / "actions.json"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Hyperparameters
BATCH_SIZE = 32
HIDDEN_SIZE = 128
NUM_LAYERS = 2
EPOCHS = 60
LEARNING_RATE = 1e-3
DROPOUT = 0.3

# ==================== Dataset Loader ====================
class SignDataset(Dataset):
    def __init__(self, sequences, labels):
        self.sequences = torch.tensor(sequences, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.sequences[idx], self.labels[idx]

def load_data():
    with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
        actions = json.load(f)["actions"]
        
    action_map = {action: idx for idx, action in enumerate(actions)}
    
    sequences, labels = [], []
    print("⏳ در حال بارگذاری فریم‌های ذخیره‌شده...")

    for action in actions:
        action_path = DATA_PATH / action
        if not action_path.exists():
            continue
            
        for seq_folder in sorted(os.listdir(action_path)):
            seq_path = action_path / seq_folder
            if not seq_path.is_dir():
                continue
                
            window = []
            files = sorted(os.listdir(seq_path), key=lambda x: int(Path(x).stem) if Path(x).stem.isdigit() else 0)
            
            for frame_file in files:
                res = np.load(seq_path / frame_file)
                window.append(res)
                
            sequences.append(window)
            labels.append(action_map[action])

    X = np.array(sequences)
    y = np.array(labels)
    
    print(f"✅ بارگذاری تکمیل شد: {X.shape[0]} توالی حرکتی، با طول توالی {X.shape[1]} و ابعاد ویژگی {X.shape[2]}")
    return X, y, actions

# ==================== Training Pipeline ====================
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Device مورد استفاده: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    X, y, actions = load_data()
    
    # Split Train / Validation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    train_dataset = SignDataset(X_train, y_train)
    val_dataset = SignDataset(X_val, y_val)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    sequence_length = X.shape[1]
    input_size = X.shape[2]
    num_classes = len(actions)

    model = SignLanguageBiLSTM(
        input_size=input_size,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        num_classes=num_classes,
        dropout=DROPOUT
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    history = {'train_loss': [], 'val_loss': [], 'val_acc': []}
    best_val_loss = float('inf')
    best_val_acc = 0.0

    print("\n🔥 شروع آموزش مدل...")
    for epoch in range(1, EPOCHS + 1):
        # Phase Train
        model.train()
        train_loss = 0.0
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * batch_x.size(0)

        train_loss /= len(train_loader.dataset)

        # Phase Validation
        model.eval()
        val_loss = 0.0
        correct = 0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item() * batch_x.size(0)
                
                preds = torch.argmax(outputs, dim=1)
                correct += (preds == batch_y).sum().item()

        val_loss /= len(val_loader.dataset)
        val_acc = (correct / len(val_loader.dataset)) * 100
        scheduler.step(val_loss)

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)

        if epoch % 5 == 0 or epoch == 1:
            print(f"Epoch [{epoch:02d}/{EPOCHS}] | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")

        # ذخیره بهترین وزن‌ها بر اساس کمترین Validation Loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            torch.save({
                'model_state_dict': model.state_dict(),
                'input_size': input_size,
                'hidden_size': HIDDEN_SIZE,
                'num_layers': NUM_LAYERS,
                'num_classes': num_classes,
                'actions': actions
            }, MODELS_DIR / "best_model.pth")

    print(f"\n🎉 آموزش تمام شد! کمترین Validation Loss: {best_val_loss:.4f} (دقت متناظر: {best_val_acc:.2f}%)")
    print(f"💾 مدل در مسیر {MODELS_DIR / 'best_model.pth'} ذخیره شد.")

    # ذخیره نمودار
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.plot(history['train_loss'], label='Train Loss')
    plt.plot(history['val_loss'], label='Val Loss')
    plt.legend()
    plt.title('Loss Curve')

    plt.subplot(1, 2, 2)
    plt.plot(history['val_acc'], label='Val Accuracy', color='green')
    plt.legend()
    plt.title('Accuracy Curve')
    plt.savefig(MODELS_DIR / "training_result.png")
    print(f"📊 نمودار عملکرد در {MODELS_DIR / 'training_result.png'} ذخیره شد.")

if __name__ == "__main__":
    main()
