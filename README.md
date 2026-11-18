# ClipGenius AI

A starter AI auto-clipper web app. It transcribes speech with the open-source
Whisper tiny model, ranks transcript moments with a lightweight heuristic,
then exports vertical 9:16 MP4 clips using FFmpeg.

## Run on Replit
1. Create a Python Repl.
2. Upload/extract this project into the Repl.
3. Ensure FFmpeg is installed (the included `replit.nix` requests it).
4. In the Shell run: `pip install -r requirements.txt`
5. Run: `uvicorn app:app --host 0.0.0.0 --port 3000`
6. Open the web preview.

## Important
- This is an MVP, not a finished commercial-grade AI editor.
- Whisper's first run downloads the tiny model and may take time.
- Free hosting may sleep, limit CPU/RAM, upload size, or execution time.
- Long videos can exceed free compute limits. Start with a short video.
- The moment picker is transcript-based scoring, not a generative AI model.
- Review every clip before publishing. Keep rights to the videos you upload.
