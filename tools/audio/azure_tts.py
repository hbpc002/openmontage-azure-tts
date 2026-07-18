"""Azure TTS provider tool — wraps tts-express script with SSML support."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class AzureTTS(BaseTool):
    name = "azure_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "azure"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:tts-express"]
    install_instructions = (
        "Ensure tts-express is installed and configured:\n"
        "  pip install tts-express\n"
        "Or copy the script to ~/.local/bin/tts-express\n"
        "Then configure Azure key in ~/.config/tts-express/config.yaml"
    )
    fallback = "piper_tts"
    fallback_tools = ["piper_tts"]
    agent_skills = ["azure-tts-docs"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "ssml_support",
        "emotion_control",
        "speed_pitch_control",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": True,
        "emotion_styles": True,
    }
    best_for = [
        "Chinese narration (best-in-class zh-CN voices)",
        "expressive narration with emotion control",
        "SSML-based fine-grained speed/pitch/pause control",
    ]
    not_good_for = [
        "fully offline production",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize. Supports SSML-style markers like [语速:-3%] [情绪:cheerful] [声音:zh-CN-XiaochenMultilingualNeural] [停顿:0.5s]"},
            "voice": {
                "type": "string",
                "default": "zh-CN-XiaochenMultilingualNeural",
                "description": "Azure voice name. Default Xiaochen (#4) for best Chinese+English. Alternates: zh-CN-Yunyi:DragonHDFlashLatestNeural (#6)",
            },
            "rate": {
                "type": "string",
                "default": "-2%",
                "description": "Speaking rate adjustment (-50% to +100%). User prefers -3%~-2% overall, slower is better.",
            },
            "format": {
                "type": "string",
                "default": "audio-24khz-48kbitrate-mono-mp3",
                "enum": ["audio-24khz-48kbitrate-mono-mp3", "audio-24khz-96kbitrate-mono-mp3", "audio-16khz-32kbitrate-mono-mp3"],
                "description": "Azure output audio format.",
            },
            "output_path": {"type": "string", "description": "Path to write the audio file."},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["text", "voice", "rate", "format"]
    side_effects = ["writes audio file to output_path", "calls Azure TTS API"]
    user_visible_verification = ["Listen to generated audio for intelligibility and tone"]

    def __init__(self) -> None:
        super().__init__()
        self._tts_express = self._find_tts_express()

    @staticmethod
    def _find_tts_express() -> str:
        """Locate the tts-express script."""
        candidates = [
            os.path.expanduser("~/.local/bin/tts-express"),
            os.path.expanduser("~/tts-express"),
            "/usr/local/bin/tts-express",
        ]
        # Also check PATH
        which = subprocess.run(["which", "tts-express"], capture_output=True, text=True, timeout=5)
        if which.returncode == 0:
            return which.stdout.strip()
        for c in candidates:
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return "tts-express"  # fallback, will fail with a clear error

    def get_status(self) -> ToolStatus:
        if not self._find_tts_express():
            return ToolStatus.UNAVAILABLE
        # Check if Azure key is configured
        config_file = os.path.expanduser("~/.config/tts-express/config.yaml")
        if os.path.isfile(config_file) or os.environ.get("AZURE_TTS_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Azure TTS is ~$1 per 1M characters for neural voices
        return round(len(inputs.get("text", "")) * 0.000001, 6)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        tts_bin = self._find_tts_express()
        if not tts_bin or not os.path.isfile(tts_bin):
            return ToolResult(
                success=False,
                error=(
                    "tts-express not found. Install it:\n"
                    "  cp ~/.local/bin/tts-express ~/.local/bin/\n"
                    "And configure ~/.config/tts-express/config.yaml with your Azure key."
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, tts_bin)
        except Exception as exc:
            return ToolResult(success=False, error=f"Azure TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], tts_bin: str) -> ToolResult:
        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        voice = inputs.get("voice", "zh-CN-XiaochenMultilingualNeural")
        rate = inputs.get("rate", "-2%")
        fmt = inputs.get("format", "audio-24khz-48kbitrate-mono-mp3")

        output_path = Path(inputs.get("output_path", "azure_tts.mp3"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build text with voice and rate markers if not already present
        has_markers = "[声音" in text or "[语速" in text or "[情绪" in text
        if has_markers:
            # Text already has inline SSML markers — pass as-is
            payload = text
        else:
            # Prepend default voice/rate markers
            payload = f"[声音:{voice}] [语速:{rate}]\n{text}"

        # Write text to temp file for tts-express
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(payload)
            txt_path = f.name

        try:
            cmd = [tts_bin, "-f", txt_path, "-o", str(output_path), "--format", fmt]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"tts-express failed (exit {proc.returncode}): {proc.stderr or proc.stdout}",
                )
        finally:
            os.unlink(txt_path)

        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice,
                "rate": rate,
                "format": fmt,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=f"azure-tts/{voice}",
        )