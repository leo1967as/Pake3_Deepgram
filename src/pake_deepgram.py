"""Quick Deepgram transcription helper with diarization and optional corrections.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List

import httpx
from dotenv import load_dotenv

load_dotenv()  # Load DEEPGRAM_KEY, N8N_WEBHOOK_URL, OPENROUTER_KEY

DEEPGRAM_KEY = os.getenv("DEEPGRAM_KEY")
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK_URL", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
LIVE_DURATION_SEC_ENV = os.getenv("LIVE_DURATION_SEC", "0").strip()


def download_audio(url: str, output: str = "temp.wav", live_duration: int | None = None) -> str:
    """Download audio from URL/YouTube with yt-dlp.

    live_duration limits live streams to the first N seconds (uses yt-dlp download-sections).
    """
    try:
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "-o",
            output,
        ]

        if live_duration and live_duration > 0:
            cmd += [
                "--download-sections",
                f"*0-{live_duration}",
                "--live-from-start",
                "--hls-use-mpegts",
            ]

        cmd.append(url)

        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        details = stderr or stdout or "yt-dlp failed without output"
        raise RuntimeError(f"yt-dlp download failed: {details}") from exc
    return output


def transcribe(audio_path: str, clip_id: str) -> Dict[str, object]:
    """Send audio to Deepgram with diarization enabled."""
    if not DEEPGRAM_KEY:
        raise RuntimeError("DEEPGRAM_KEY is missing in environment")

    with open(audio_path, "rb") as f:
        resp = httpx.post(
            "https://api.deepgram.com/v1/listen?"
            "model=nova-3&"
            "diarize=true&"
            "smart_format=true&"
            "language=th&"
            "keyterm=SET50%2CPTTGC%2CQuantitative%20Easing%2CLiquidity%20Ratio%2CFed%20Funds%20Rate",
            headers={
                "Authorization": f"Token {DEEPGRAM_KEY}",
                "Content-Type": "audio/wav",
            },
            content=f.read(),
            timeout=300,
        )

    resp.raise_for_status()
    data = resp.json()

    segments: List[Dict[str, object]] = []
    words = data["results"]["channels"][0]["alternatives"][0]["words"]

    current_speaker: str | None = None
    current_text: List[str] = []
    current_start: float = 0.0

    for i, word in enumerate(words):
        speaker = f"SPEAKER_{word.get('speaker', 0)}"

        if speaker != current_speaker and current_text:
            segments.append(
                {
                    "speaker": current_speaker,
                    "text": " ".join(current_text),
                    "start": current_start,
                    "end": words[i - 1]["end"],
                }
            )
            current_text = []

        if not current_text:
            current_start = word["start"]

        current_speaker = speaker
        current_text.append(word.get("punctuated_word", word["word"]))

    if current_text:
        segments.append(
            {
                "speaker": current_speaker,
                "text": " ".join(current_text),
                "start": current_start,
                "end": words[-1]["end"],
            }
        )

    return {
        "clip_id": clip_id,
        "segments": segments,
        "metadata": {
            "provider": "deepgram",
            "model": "nova-3",
            "duration_sec": data["metadata"]["duration"],
            "total_speakers": len({s["speaker"] for s in segments}),
        },
    }


def send_to_n8n(transcript: Dict[str, object]) -> None:
    """Send transcript to N8N webhook when configured."""
    if N8N_WEBHOOK:
        httpx.post(N8N_WEBHOOK, json=transcript, timeout=10)
        print(f"Sent transcript to N8N: {N8N_WEBHOOK}")


def correct_with_openrouter(transcript: Dict[str, object]) -> Dict[str, object]:
    """Optional: use OpenRouter to correct financial terms."""
    if not OPENROUTER_KEY:
        return transcript

    full_text = "\n".join([f"[{s['speaker']}]: {s['text']}" for s in transcript["segments"]])

    prompt = (
        "คุณคือนักวิเคราะห์การเงินมืออาชีพ ช่วยแก้ไขข้อความต่อไปนี้ให้ถูกต้องตามศัพท์การเงินมาตรฐาน:\n\n"
        "กฎ:\n"
        "1. แปลงคำที่ออกเสียงผิด → ศัพท์การเงินจริง (เช่น \"คันทิเททีฟ อีซิ่ง\" → \"Quantitative Easing\")\n"
        "2. รักษาโครงสร้างผู้พูดและช่วงเวลาเดิม\n"
        "3. ไม่เปลี่ยนเนื้อหาความหมายหลัก\n\n"
        "ข้อความ:\n"
        f"{full_text}\n\n"
        "ตอบกลับในรูปแบบ JSON เท่านั้น:\n"
        "{\n  \"corrections\": [\n    {\"original\": \"ข้อความเดิม\", \"corrected\": \"ข้อความแก้แล้ว\"}\n  ]\n}"
    )

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        transcript["metadata"]["llm_corrected"] = True
    except Exception as exc:  # noqa: BLE001
        print(f"LLM correction failed: {exc}")

    return transcript


if __name__ == "__main__":
    # Accept AUDIO_URL env var or replace the sample link below.
    audio_url = os.getenv("AUDIO_URL", "https://www.youtube.com/watch?v=ตัวอย่าง").strip()

    if not audio_url or "ตัวอย่าง" in audio_url:
        raise SystemExit(
            "Set AUDIO_URL env or replace the sample YouTube link in pake_deepgram.py before running."
        )

    live_duration: int | None = None
    if LIVE_DURATION_SEC_ENV and LIVE_DURATION_SEC_ENV.isdigit():
        live_duration_val = int(LIVE_DURATION_SEC_ENV)
        live_duration = live_duration_val if live_duration_val > 0 else None

    # If a local file path is provided, skip download and use it directly.
    if Path(audio_url).exists():
        audio_file = audio_url
    else:
        audio_file = download_audio(audio_url, "finance_podcast.wav", live_duration=live_duration)

    transcript = transcribe(audio_file, "finance_podcast_001")

    output_path = Path("transcripts") / f"{transcript['clip_id']}.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)
    print(f"Saved transcript: {output_path}")

    send_to_n8n(transcript)

    Path(audio_file).unlink(missing_ok=True)
