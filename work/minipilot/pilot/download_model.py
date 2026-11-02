"""Download only the approved free, pinned local Qwen model."""
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    print(snapshot_download('mlx-community/Qwen2.5-VL-3B-Instruct-4bit',
          revision='46d4cf06a06ffc1a766c214174f9cbed2f45bcab',
          local_dir=str(ROOT/'models/qwen2.5-vl-3b-4bit'),max_workers=3))
