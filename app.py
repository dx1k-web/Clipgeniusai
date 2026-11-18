import os, uuid, shutil, subprocess, re
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = FastAPI(title="ClipGenius AI")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-1800:])
    return p.stdout

def get_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(out.strip())

def transcribe(path):
    # Lazy-load a small open-source Whisper model.
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path), vad_filter=True)
    return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
            for s in segments if s.text.strip()]

def choose_moments(segments, duration, max_clips=5, clip_len=35):
    # Lightweight transcript-based scoring. This is a practical starter,
    # not a claim of human-level semantic understanding.
    candidates = []
    hooks = ["why", "how", "secret", "mistake", "best", "worst", "never",
             "always", "important", "because", "actually", "imagine",
             "surprising", "problem", "solution", "learn", "tip"]
    for i, s in enumerate(segments):
        text = s["text"].lower()
        words = re.findall(r"\w+", text)
        score = min(len(words), 24) / 8
        score += sum(1.2 for h in hooks if h in text)
        score += 0.8 if "?" in s["text"] else 0
        score += 0.5 if "!" in s["text"] else 0
        # Prefer a complete thought; avoid extremely short fragments.
        if len(words) >= 5:
            start = max(0, s["start"] - 5)
            end = min(duration, max(s["end"] + 22, start + 18))
            end = min(end, start + clip_len)
            if end - start >= 10:
                candidates.append((score, start, end, s["text"]))
    candidates.sort(reverse=True)
    chosen=[]
    for score, start, end, text in candidates:
        if all(end <= a or start >= b for a,b,_ in chosen):
            chosen.append((start,end,text))
        if len(chosen) >= max_clips:
            break
    if not chosen and duration > 0:
        start=0
        chosen=[(start,min(duration,clip_len),"Auto-selected video segment")]
    return sorted(chosen)

@app.post("/api/clip")
async def create_clips(video: UploadFile = File(...)):
    if not video.filename:
        raise HTTPException(400, "Please choose a video.")
    ext=Path(video.filename).suffix.lower()
    if ext not in [".mp4",".mov",".m4v",".webm"]:
        raise HTTPException(400, "Supported formats: MP4, MOV, M4V, WEBM.")
    job=uuid.uuid4().hex[:10]
    source=UPLOADS/f"{job}{ext}"
    with source.open("wb") as f:
        shutil.copyfileobj(video.file,f)
    try:
        duration=get_duration(source)
        if duration > 3600:
            raise HTTPException(400,"For the free demo, please use a video under 60 minutes.")
        segments=transcribe(source)
        if not segments:
            raise RuntimeError("No speech detected. Please try a video with clear spoken audio.")
        moments=choose_moments(segments,duration)
        results=[]
        for i,(start,end,caption) in enumerate(moments,1):
            out=OUTPUTS/f"{job}_clip_{i}.mp4"
            run(["ffmpeg","-y","-ss",str(start),"-i",str(source),"-t",str(end-start),
                 "-vf","scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
                 "-c:v","libx264","-preset","veryfast","-crf","24",
                 "-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)])
            results.append({"name":f"Clip {i}","start":round(start,1),"end":round(end,1),
                            "text":caption,"url":f"/api/download/{out.name}"})
        return {"clips":results,"message":"Clips are ready! Review them before publishing."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")
    finally:
        try: source.unlink(missing_ok=True)
        except: pass

@app.get("/api/download/{filename}")
def download(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(400,"Invalid filename")
    path=OUTPUTS/filename
    if not path.exists():
        raise HTTPException(404,"Clip not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)
