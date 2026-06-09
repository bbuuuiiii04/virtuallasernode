import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dense_cue_breakpoints as dense

def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        root = Path("captures/fixture_model")
        
    if not root.exists():
        print(f"Error: {root} does not exist.")
        return

    print("Scanning for existing captures...")
    capture_dirs = []
    for d in root.rglob("*"):
        if d.is_dir() and ((d / "video.mp4").exists() or (d / "video_color.mp4").exists()):
            capture_dirs.append(d)
            
    total = len(capture_dirs)
    print(f"Found {total} captures to process at 60 FPS.")
    
    if total == 0:
        return

    ANALYSIS_FPS = 60
    THRESHOLD = 50
    
    start_time = time.time()
    
    for i, folder in enumerate(capture_dirs, 1):
        video_path = folder / "video.mp4" if (folder / "video.mp4").exists() else folder / "video_color.mp4"
        
        try:
            with open(folder / "metadata.json", "r") as f:
                metadata = json.load(f)
            
            # Methodically map metadata to exactly what the analyzer expects from manifest.jsonl
            entry = {
                "capture": str(video_path),
                "capture_dir": str(folder),
                "folder": str(folder.relative_to(root)),
                "full_ch1_19_dmx": {str(k).replace("CH", ""): v for k, v in metadata.get("ch1_19", {}).items()},
                "family": metadata.get("family", ""),
                "duration": metadata.get("duration", 3.0)
            }
            
            res = dense.analyze_existing_entry(entry, ANALYSIS_FPS, THRESHOLD)
            with open(folder / "analysis.json", "w") as f:
                json.dump(res["analysis"], f, indent=2)
        except Exception as e:
            print(f"[{i}/{total}] Error processing {folder.name}: {e}")
            
        # Print progress every 10 items to avoid flooding the log
        if i % 10 == 0 or i == total:
            elapsed = time.time() - start_time
            rate = i / elapsed
            eta = (total - i) / rate if rate > 0 else 0
            
            bar_len = 30
            filled = int(bar_len * i / total)
            bar = '=' * filled + '-' * (bar_len - filled)
            
            print(f"[{bar}] {i}/{total} ({i/total*100:.1f}%) | "
                  f"Rate: {rate:.2f} clips/s | ETA: {eta/60:.1f} mins | "
                  f"Processing: {folder.name}")

if __name__ == "__main__":
    main()
