"""Automatic Video Recording Suite for Demo Segments.

Automates unattended video recording of the demo terminal:
- Mode 1: FFmpeg desktop recording with gdigrab in a new maximized dark-themed terminal
- Mode 2: Playwright browser fallback streaming real stdout to a styled dark HTML terminal (1920x1080)
- Visible countdown (5, 4, 3, 2, 1) and 2-second lead-in/lead-out padding
- Graceful 'q' stdin termination ensuring finalized, valid MP4 video containers
- Appends video filenames and chapter offsets to demo/logs/timeline_<timestamp>.txt
- Frame extraction for video verification

Additive only: does not alter pipeline code, rubric, prompts, or test fixtures.
"""

import argparse
from datetime import datetime
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

SEGMENT_NAMES = {
    "1": "Live end-to-end run",
    "2": "Deliberate error caught",
    "3": "Evaluator catch-rate (live)",
    "4": "Memory demo",
    "5": "Safe fallback replays",
}


def find_ffmpeg() -> Tuple[Optional[str], Optional[str]]:
    """Locate ffmpeg and ffprobe executables on system PATH or common Windows locations."""
    ffmpeg_cmd = shutil.which("ffmpeg")
    ffprobe_cmd = shutil.which("ffprobe")

    if ffmpeg_cmd and ffprobe_cmd:
        return ffmpeg_cmd, ffprobe_cmd

    # Search WinGet package paths and Program Files
    candidate_dirs = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        Path("C:/Program Files/ffmpeg/bin"),
        Path("C:/ProgramData/chocolatey/bin"),
    ]

    for cdir in candidate_dirs:
        if cdir.exists():
            for f in cdir.glob("**/ffmpeg.exe"):
                prob = f.parent / "ffprobe.exe"
                if prob.exists():
                    return str(f), str(prob)
                elif f.exists():
                    return str(f), str(shutil.which("ffprobe") or f.parent / "ffprobe.exe")

    return ffmpeg_cmd, ffprobe_cmd


def is_gdigrab_available(ffmpeg_cmd: str) -> bool:
    """Test if gdigrab can capture the desktop in the current session (not blocked by error 5)."""
    try:
        cmd = [
            ffmpeg_cmd,
            "-f", "gdigrab",
            "-t", "0.2",
            "-i", "desktop",
            "-f", "null",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if "Failed to capture image" in res.stderr or "error 5" in res.stderr:
            return False
        return res.returncode == 0
    except Exception:
        return False


def probe_video(video_path: Path, ffprobe_cmd: str) -> Dict[str, str]:
    """Extract duration, resolution, size, and bitrate using ffprobe."""
    info = {
        "duration": "unknown",
        "resolution": "unknown",
        "size_mb": f"{video_path.stat().st_size / (1024 * 1024):.2f} MB",
    }
    if not Path(ffprobe_cmd).exists() and not shutil.which(ffprobe_cmd):
        return info

    try:
        cmd = [
            ffprobe_cmd,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json",
            str(video_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        stream = data["streams"][0]
        w = stream.get("width", "?")
        h = stream.get("height", "?")
        dur = float(stream.get("duration", 0))
        m, s = divmod(int(dur), 60)
        info["duration"] = f"{m:02d}:{s:02d} ({dur:.1f}s)"
        info["resolution"] = f"{w}x{h}"
        info["duration_sec"] = dur
    except Exception as e:
        info["error"] = str(e)
    return info


def extract_middle_frame(video_path: Path, output_png: Path, ffmpeg_cmd: str, ffprobe_cmd: str) -> bool:
    """Extract one representative frame from the middle of the video for verification."""
    dur_sec = 5.0
    info = probe_video(video_path, ffprobe_cmd)
    if "duration_sec" in info and info["duration_sec"] > 2:
        dur_sec = info["duration_sec"] / 2.0

    cmd = [
        ffmpeg_cmd,
        "-y",
        "-ss", str(dur_sec),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_png),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_png.exists() and output_png.stat().st_size > 0
    except Exception as e:
        console.print(f"[bold red]Frame extraction error: {e}[/bold red]")
        return False


def terminate_tree(pid: int):
    """Force terminate process tree cleanly on Windows or Unix."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception:
        pass


def record_segment_ffmpeg(
    seg_id: str,
    countdown: int,
    pause: float,
    max_wait: int,
    fps: int,
    ffmpeg_cmd: str,
    ffprobe_cmd: str,
    output_dir: Path,
    timeline_lines: List[str],
    timeline_path: Path,
    session_start_time: float,
) -> Tuple[bool, Path]:
    """Execute Mode 1: Screen-record dedicated maximized terminal running the segment."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_mp4 = output_dir / f"segment{seg_id}_{timestamp}.mp4"
    logs_dir = Path("demo/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    sentinel_done = logs_dir / f".segment_{seg_id}_{timestamp}.done"

    seg_name = SEGMENT_NAMES.get(seg_id, f"Segment {seg_id}")
    console.print(
        Panel(
            f"[bold cyan]AUTOMATIC RECORDING: SEGMENT {seg_id} - {seg_name.upper()}[/bold cyan]\n"
            f"Output Video:  [bold green]{output_mp4}[/bold green]\n"
            f"Mode:          [magenta]FFmpeg Desktop Screen Capture (gdigrab, {fps} fps)[/magenta]\n"
            f"Countdown:     [yellow]{countdown} seconds[/yellow] in target terminal",
            border_style="cyan",
        )
    )

    # Build runner powershell script
    ps_script_path = logs_dir / f"run_segment_{seg_id}_{timestamp}.ps1"
    script_lines = [
        '$Host.UI.RawUI.WindowTitle = "Autonomous Lesson Generator Demo - Recording Terminal"',
        '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8',
        'Clear-Host',
        'Write-Host ""',
        f'Write-Host "========================================================================" -ForegroundColor Cyan',
        f'Write-Host "   AUTONOMOUS DEMO RECORDING: SEGMENT {seg_id} ({seg_name})" -ForegroundColor Yellow',
        f'Write-Host "========================================================================" -ForegroundColor Cyan',
        'Write-Host ""',
    ]

    for c in range(countdown, 0, -1):
        script_lines.append(f'Write-Host ">>> RECORDING STARTS IN {c}... <<<" -ForegroundColor Yellow')
        script_lines.append('Start-Sleep -Seconds 1')

    script_lines.extend([
        'Write-Host ">>> [REC] RECORDING LIVE NOW <<<" -ForegroundColor Red',
        'Start-Sleep -Seconds 2',  # 2s lead-in padding
        f'& "{sys.executable}" demo/record_demo.py --segment {seg_id} --auto --pause {pause} --max-wait {max_wait}',
        '$exitCode = $LASTEXITCODE',
        'Start-Sleep -Seconds 2',  # 2s lead-out padding
        'Write-Host ""',
        'Write-Host ">>> [STOP] SEGMENT RECORDING COMPLETED <<<" -ForegroundColor Green',
        'Start-Sleep -Seconds 1',
        f'Set-Content -Path "{sentinel_done}" -Value "$exitCode"',
    ])

    ps_script_path.write_text("\r\n".join(script_lines), encoding="utf-8")

    # Start ffmpeg desktop recorder
    ffmpeg_cmd_args = [
        ffmpeg_cmd,
        "-y",
        "-f", "gdigrab",
        "-framerate", str(fps),
        "-i", "desktop",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_mp4),
    ]

    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(1.0)  # Let ffmpeg initialize recording pipe

    # Launch new terminal window
    wt_cmd = shutil.which("wt")
    term_proc = None
    if wt_cmd:
        term_proc = subprocess.Popen(
            [
                wt_cmd,
                "--maximized",
                "-d", str(project_root),
                "powershell.exe",
                "-NoExit",
                "-ExecutionPolicy", "Bypass",
                "-File", str(ps_script_path.resolve()),
            ]
        )
    else:
        term_proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoExit",
                "-ExecutionPolicy", "Bypass",
                "-File", str(ps_script_path.resolve()),
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    seg_start_offset = time.time() - session_start_time
    start_rec = time.time()
    max_recording_time = max_wait + countdown + 30

    console.print(f"[bold red]● Recording desktop...[/bold red] Waiting for segment {seg_id} completion.")

    # Wait for sentinel file
    record_status = "ok"
    try:
        while True:
            if sentinel_done.exists():
                time.sleep(1.0)
                break
            if time.time() - start_rec > max_recording_time:
                console.print("[bold yellow]Max wait timeout reached in recording loop.[/bold yellow]")
                record_status = "timeout"
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("[yellow]Recording interrupted by user.[/yellow]")
        record_status = "interrupted"

    # Stop ffmpeg gracefully by sending 'q' to stdin
    try:
        if ffmpeg_proc.stdin:
            ffmpeg_proc.stdin.write(b"q\n")
            ffmpeg_proc.stdin.flush()
        ffmpeg_proc.wait(timeout=8)
    except Exception:
        terminate_tree(ffmpeg_proc.pid)

    # Clean up runner script
    try:
        if sentinel_done.exists():
            sentinel_done.unlink()
        if ps_script_path.exists():
            ps_script_path.unlink()
    except Exception:
        pass

    duration = time.time() - start_rec
    seg_end_offset = time.time() - session_start_time

    # Record timeline
    timeline_entry = (
        f"Segment {seg_id}: {seg_name} | "
        f"File: {output_mp4.name} | "
        f"Start: {int(seg_start_offset)//60:02d}:{int(seg_start_offset)%60:02d} | "
        f"Duration: {int(duration)//60:02d}:{int(duration)%60:02d} | "
        f"Status: {record_status}"
    )
    timeline_lines.append(timeline_entry)
    timeline_path.write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")

    return output_mp4.exists() and output_mp4.stat().st_size > 0, output_mp4


def ansi_to_html(text: str) -> str:
    """Convert ANSI escape color codes into styled HTML spans for browser stream."""
    color_map = {
        "30": "#6b7280", "31": "#ef4444", "32": "#10b981", "33": "#f59e0b",
        "34": "#3b82f6", "35": "#a855f7", "36": "#06b6d4", "37": "#f3f4f6",
        "90": "#9ca3af", "91": "#f87171", "92": "#34d399", "93": "#fbbf24",
        "94": "#60a5fa", "95": "#c084fc", "96": "#22d3ee", "97": "#ffffff",
    }
    escaped = html.escape(text)

    def repl(m):
        raw = m.group(1)
        if not raw or raw in ("0", "00"):
            return "</span>"
        codes = raw.split(";")
        styles = []
        for c in codes:
            if c in color_map:
                styles.append(f"color:{color_map[c]}")
            elif c == "1":
                styles.append("font-weight:700")
            elif c == "2":
                styles.append("opacity:0.75")
        if styles:
            return f'<span style="{";".join(styles)}">'
        return ""

    return re.sub(r"\x1b\[([0-9;]*)m", repl, escaped)


def record_segment_browser(
    seg_id: str,
    pause: float,
    max_wait: int,
    ffmpeg_cmd: Optional[str],
    output_dir: Path,
    timeline_lines: List[str],
    timeline_path: Path,
    session_start_time: float,
) -> Tuple[bool, Path]:
    """Execute Mode 2: Stream stdout into styled HTML page and record with Playwright video."""
    from playwright.sync_api import sync_playwright

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seg_name = SEGMENT_NAMES.get(seg_id, f"Segment {seg_id}")
    final_mp4 = output_dir / f"segment{seg_id}_{timestamp}.mp4"
    temp_video_dir = output_dir / f".temp_vid_{timestamp}"
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold cyan]AUTOMATIC RECORDING: SEGMENT {seg_id} - {seg_name.upper()} (BROWSER FALLBACK)[/bold cyan]\n"
            f"Streaming real stdout to dark terminal web page recorded by Playwright (1920x1080).",
            border_style="cyan",
        )
    )

    html_file = Path("demo/logs") / f"terminal_stream_{timestamp}.html"
    initial_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Terminal Stream</title>
<style>
  body {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
    font-size: 18px;
    line-height: 1.45;
    margin: 0;
    padding: 24px 24px 60px 24px;
    box-sizing: border-box;
    overflow-x: hidden;
  }
  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
  }
  #status-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: #161b22;
    border-top: 1px solid #30363d;
    padding: 10px 24px;
    font-family: inherit;
    font-size: 16px;
    font-weight: bold;
    color: #38bdf8;
    z-index: 100;
  }
</style>
</head>
<body>
<pre id="term-out"></pre>
<div id="status-bar" style="display: none;"></div>
<script>
  window.appendTerminalContent = function(rawText, htmlContent) {
    const el = document.getElementById('term-out');
    const bar = document.getElementById('status-bar');

    if (rawText.includes('⏳ Elapsed')) {
      bar.style.display = 'block';
      bar.innerHTML = htmlContent;
    } else {
      el.innerHTML += htmlContent;
    }
    window.scrollTo(0, document.body.scrollHeight);
  };
</script>
</body>
</html>"""
    html_file.write_text(initial_html, encoding="utf-8")

    seg_start_offset = time.time() - session_start_time
    start_rec = time.time()
    record_status = "ok"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(temp_video_dir),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.goto(html_file.resolve().as_uri())

        time.sleep(2.0)  # 2s lead-in padding

        # Run record_demo.py and stream stdout
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        cmd = [
            sys.executable,
            "demo/record_demo.py",
            "--segment", seg_id,
            "--auto",
            "--pause", str(pause),
            "--max-wait", str(max_wait),
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )

        for line in proc.stdout:
            html_line = ansi_to_html(line)
            page.evaluate("([raw, html]) => window.appendTerminalContent(raw, html)", [line, html_line])

        proc.wait()
        time.sleep(2.0)  # 2s lead-out padding

        page.close()
        context.close()
        browser.close()

    # Find recorded webm
    recorded_webm = None
    for f in temp_video_dir.glob("*.webm"):
        recorded_webm = f
        break

    if not recorded_webm:
        return False, final_mp4

    # Convert to mp4 if ffmpeg exists
    if ffmpeg_cmd and (Path(ffmpeg_cmd).exists() or shutil.which(ffmpeg_cmd)):
        subprocess.run(
            [
                ffmpeg_cmd,
                "-y",
                "-i", str(recorded_webm),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "veryfast",
                str(final_mp4),
            ],
            capture_output=True,
        )
        shutil.rmtree(temp_video_dir, ignore_errors=True)
        target_video = final_mp4
    else:
        # Keep webm as fallback
        webm_dest = output_dir / f"segment{seg_id}_{timestamp}.webm"
        shutil.move(str(recorded_webm), str(webm_dest))
        shutil.rmtree(temp_video_dir, ignore_errors=True)
        target_video = webm_dest

    duration = time.time() - start_rec
    timeline_entry = (
        f"Segment {seg_id}: {seg_name} | "
        f"File: {target_video.name} | "
        f"Start: {int(seg_start_offset)//60:02d}:{int(seg_start_offset)%60:02d} | "
        f"Duration: {int(duration)//60:02d}:{int(duration)%60:02d} | "
        f"Status: {record_status}"
    )
    timeline_lines.append(timeline_entry)
    timeline_path.write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")

    return target_video.exists() and target_video.stat().st_size > 0, target_video


def main():
    parser = argparse.ArgumentParser(
        description="Automatic Video Recording Suite for Demo Segments"
    )
    parser.add_argument(
        "--segment",
        type=str,
        choices=["1", "2", "3", "4", "5", "all"],
        default="5",
        help="Segment to record (1-5 or all; default: 5)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["ffmpeg", "browser"],
        default="ffmpeg",
        help="Recording mode: 'ffmpeg' (desktop recording) or 'browser' (Playwright web stream fallback)",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=5,
        help="Seconds of visible countdown in terminal before recording starts (default: 5)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=3.0,
        help="Narration pause length in seconds after tables, quotes, and cards (default: 3.0)",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=360,
        help="Max wait timeout in seconds (default: 360)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Video recording framerate (default: 30)",
    )
    parser.add_argument(
        "--extract-frame",
        type=str,
        default=None,
        help="Path to save extracted middle frame image from video",
    )

    args = parser.parse_args()

    ffmpeg_cmd, ffprobe_cmd = find_ffmpeg()

    # Pre-flight FFmpeg check
    if args.mode == "ffmpeg" and not ffmpeg_cmd:
        console.print(
            Panel(
                "[bold red]FFmpeg is not installed or not in PATH.[/bold red]\n\n"
                "To record real desktop terminals via Mode 1, FFmpeg is required.\n"
                "Install it on Windows via:\n"
                "  [bold yellow]winget install Gyan.FFmpeg[/bold yellow]\n\n"
                "Or run in browser fallback mode (no FFmpeg required):\n"
                "  [bold green]python demo/auto_record.py --segment 5 --mode browser[/bold green]",
                title="[bold yellow]FFmpeg Dependency Required[/bold yellow]",
                border_style="red",
            )
        )
        sys.exit(2)

    # If Mode 1 is requested, check if desktop capture is available in this session
    mode_to_use = args.mode
    if args.mode == "ffmpeg":
        if not is_gdigrab_available(ffmpeg_cmd):
            console.print(
                "[bold yellow]Notice: Desktop GDI screen capture is not accessible in this background session (Error 5: Access Denied). "
                "Automatically using Mode 2 (Browser terminal capture recorded with Playwright and converted with FFmpeg to 1080p MP4).[/bold yellow]\n"
            )
            mode_to_use = "browser"

    # Ensure demo/videos directory exists
    video_dir = Path("demo/videos")
    video_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = Path("demo/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    timeline_path = logs_dir / f"timeline_{session_ts}.txt"
    timeline_lines = [
        "# Automated Demo Recording Session Timeline",
        f"# Session Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# Format: Segment <id>: <name> | File: <filename> | Start: MM:SS | Duration: MM:SS | Status: <status>",
        "",
    ]

    session_start_time = time.time()
    segments = ["1", "2", "3", "4", "5"] if args.segment == "all" else [args.segment]

    for seg_id in segments:
        if mode_to_use == "ffmpeg":
            ok, vpath = record_segment_ffmpeg(
                seg_id=seg_id,
                countdown=args.countdown,
                pause=args.pause,
                max_wait=args.max_wait,
                fps=args.fps,
                ffmpeg_cmd=ffmpeg_cmd,
                ffprobe_cmd=ffprobe_cmd,
                output_dir=video_dir,
                timeline_lines=timeline_lines,
                timeline_path=timeline_path,
                session_start_time=session_start_time,
            )
        else:
            ok, vpath = record_segment_browser(
                seg_id=seg_id,
                pause=args.pause,
                max_wait=args.max_wait,
                ffmpeg_cmd=ffmpeg_cmd,
                output_dir=video_dir,
                timeline_lines=timeline_lines,
                timeline_path=timeline_path,
                session_start_time=session_start_time,
            )

        if ok:
            console.print(f"[bold green]✔ Successfully recorded Segment {seg_id}: {vpath}[/bold green]")
            if ffprobe_cmd:
                meta = probe_video(vpath, ffprobe_cmd)
                console.print(f"  Duration:   {meta.get('duration', 'N/A')}")
                console.print(f"  Resolution: {meta.get('resolution', 'N/A')}")
                console.print(f"  File Size:  {meta.get('size_mb', 'N/A')}")

            # Extract frame if requested
            if args.extract_frame:
                frame_dest = Path(args.extract_frame)
                extracted = extract_middle_frame(vpath, frame_dest, ffmpeg_cmd, ffprobe_cmd)
                if extracted:
                    console.print(f"  [cyan]Middle frame extracted: {frame_dest}[/cyan]")
        else:
            console.print(f"[bold red]✖ Recording failed for Segment {seg_id}[/bold red]")


if __name__ == "__main__":
    main()
