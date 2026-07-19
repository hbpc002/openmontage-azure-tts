"""Video cover image generator — generates multiple dramatic style/layout variants.

Uses pollinations.ai for dramatic character+scene backgrounds + ImageMagick
for large bold side-placed text overlay. The user picks their favorite.

Usage:
    from tools.graphics.cover_gen import CoverGen

    tool = CoverGen()
    result = tool.execute({
        "title": "告别ChatBot AI Agent 正在取代你的工作",
        "subtitle": "从问AI答 到派AI干",
        "tag": "科普视频",
        "output_dir": "/home/Ubuntu/",
        "count": 4,
    })
    # result.data["variants"] -> list of {path, style, layout, filename}
"""

from __future__ import annotations

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

# Dramatic backgrounds with characters: each style is a distinct mood
_STYLES: list[dict[str, Any]] = [
    {
        "name": "cyber-hero",
        "bg_prompt": (
            "cinematic shot futuristic cyborg robot warrior glowing blue eyes "
            "dark moody cyberpunk city background dramatic lighting epic "
            "no text no logo 1920x1080"
        ),
        "panel_color": "rgba(0,10,30,0.8)",  # dark blue panel behind text
        "colors": {"title": "#00d4ff", "subtitle": "white", "tag": "rgba(255,255,255,0.6)"},
    },
    {
        "name": "ai-god",
        "bg_prompt": (
            "god rays shining through clouds giant floating digital brain "
            "futuristic technology surreal dramatic cinematic epic "
            "no text no logo 1920x1080"
        ),
        "panel_color": "rgba(0,0,0,0.75)",
        "colors": {"title": "white", "subtitle": "#fbbf24", "tag": "rgba(255,255,255,0.5)"},
    },
    {
        "name": "robot-uprising",
        "bg_prompt": (
            "army of humanoid robots marching futuristic city destroyed "
            "orange fire sky dramatic apocalyptic cinematic epic "
            "no text no logo 1920x1080"
        ),
        "panel_color": "rgba(20,0,0,0.75)",
        "colors": {"title": "#ff6b35", "subtitle": "white", "tag": "rgba(255,255,255,0.5)"},
    },
    {
        "name": "matrix-green",
        "bg_prompt": (
            "hacker silhouette digital rain green code dark atmosphere "
            "futuristic cyberpunk cinematic dramatic mysterious "
            "no text no logo 1920x1080"
        ),
        "panel_color": "rgba(0,10,0,0.78)",
        "colors": {"title": "#34d399", "subtitle": "white", "tag": "rgba(255,255,255,0.5)"},
    },
    {
        "name": "ai-brain",
        "bg_prompt": (
            "glowing neon brain connected to wires abstract intelligence "
            "purple blue pink vibrant futuristic surreal dramatic "
            "no text no logo 1920x1080"
        ),
        "panel_color": "rgba(10,0,20,0.78)",
        "colors": {"title": "white", "subtitle": "#c084fc", "tag": "rgba(255,255,255,0.5)"},
    },
]

# Text layouts: text on the side, very large fonts
_LAYOUTS: list[dict[str, Any]] = [
    # LEFT side panel, text stacked top-to-bottom
    {
        "name": "left-stack",
        "panel_gravity": "west",
        "panel_width": 700,
        "items": [
            {"key": "title", "size": 110, "dy": -120, "color_override": None},
            {"key": "subtitle", "size": 64, "dy": 30, "color_override": None},
            {"key": "tag", "size": 42, "dy": 130, "color_override": None},
        ],
    },
    # RIGHT side panel, text stacked top-to-bottom
    {
        "name": "right-stack",
        "panel_gravity": "east",
        "panel_width": 700,
        "items": [
            {"key": "title", "size": 110, "dy": -120, "color_override": None},
            {"key": "subtitle", "size": 64, "dy": 30, "color_override": None},
            {"key": "tag", "size": 42, "dy": 130, "color_override": None},
        ],
    },
    # LEFT side, title huge, the rest compact
    {
        "name": "left-title-big",
        "panel_gravity": "west",
        "panel_width": 800,
        "items": [
            {"key": "title", "size": 130, "dy": -80, "color_override": None},
            {"key": "subtitle", "size": 56, "dy": 70, "color_override": None},
            {"key": "tag", "size": 38, "dy": 150, "color_override": None},
        ],
    },
    # RIGHT side, title huge
    {
        "name": "right-title-big",
        "panel_gravity": "east",
        "panel_width": 800,
        "items": [
            {"key": "title", "size": 130, "dy": -80, "color_override": None},
            {"key": "subtitle", "size": 56, "dy": 70, "color_override": None},
            {"key": "tag", "size": 38, "dy": 150, "color_override": None},
        ],
    },
]


class CoverGen(BaseTool):
    name = "cover_gen"
    version = "0.3.0"
    tier = ToolTier.ENHANCE
    capability = "cover_generation"
    provider = "pollinations"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["cmd:convert", "cmd:curl"]
    install_instructions = "Ensure ImageMagick and curl are installed."

    input_schema = {
        "type": "object",
        "required": ["title", "subtitle"],
        "properties": {
            "title": {"type": "string", "description": "Main title text"},
            "subtitle": {"type": "string", "description": "Subtitle/secondary text"},
            "tag": {"type": "string", "description": "Small tag text at bottom", "default": ""},
            "output_dir": {"type": "string", "description": "Output directory", "default": "/tmp"},
            "count": {"type": "integer", "description": "Number of variants (1-8)", "default": 4, "minimum": 1, "maximum": 8},
            "seed": {"type": "integer", "description": "Base seed", "default": 42},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    side_effects = ["writes cover images", "calls pollinations.ai API"]

    _POLLINATIONS_URL = "https://image.pollinations.ai/prompt"

    def get_status(self) -> ToolStatus:
        try:
            subprocess.run(["convert", "--version"], capture_output=True, timeout=5)
            subprocess.run(["curl", "--version"], capture_output=True, timeout=5)
        except Exception:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"CoverGen failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = 0.0
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        import urllib.parse

        title = inputs["title"]
        subtitle = inputs.get("subtitle", "")
        tag = inputs.get("tag", "")
        output_dir = Path(inputs.get("output_dir", "/tmp"))
        count = min(inputs.get("count", 4), 8)
        base_seed = inputs.get("seed", 42)

        output_dir.mkdir(parents=True, exist_ok=True)

        safe_base = title.strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_base = "".join(c for c in safe_base if c.isprintable() and c not in "<>:\"|?*！")
        if not safe_base:
            safe_base = "cover"

        variants: list[dict[str, str]] = []
        idx = 0
        n_styles = len(_STYLES)
        n_layouts = len(_LAYOUTS)

        # Distribute: count=4 -> 2 styles × 2 layouts, count=6 -> 3×2, etc.
        styles_used = min(n_styles, max(1, (count + 1) // 2))
        layouts_used = min(n_layouts, (count + styles_used - 1) // styles_used)
        styles_used = min(styles_used, count)

        W, H = 1920, 1080
        font = "Noto-Sans-CJK-SC-Bold"

        for si in range(styles_used):
            for li in range(layouts_used):
                if idx >= count:
                    break
                style = _STYLES[si]
                layout = _LAYOUTS[li]
                seed = base_seed + idx

                bg_url = f"{self._POLLINATIONS_URL}/{urllib.parse.quote(style['bg_prompt'])}?width=1024&height=576&seed={seed}"
                bg_path = output_dir / f"_bg_{seed}.jpg"
                subprocess.run(
                    ["curl", "-s", "-o", str(bg_path), bg_url],
                    capture_output=True, text=True, timeout=60,
                )

                out_name = f"{safe_base}_{style['name']}_{layout['name']}.jpg"
                out_path = output_dir / out_name

                # Build imagemagick command
                cmd = [
                    "convert", str(bg_path),
                    "-resize", f"{W}x{H}!",
                ]

                # Draw a dark semi-transparent panel on one side for text
                pw = layout["panel_width"]
                if layout["panel_gravity"] == "west":
                    # Left panel: rectangle from (0,0) to (pw, H)
                    panel_draw = f"rectangle 0,0 {pw},{H}"
                    text_gravity = "west"
                    text_dx = 50  # padding from left edge
                else:
                    # Right panel: rectangle from (W-pw, 0) to (W, H)
                    panel_draw = f"rectangle {W-pw},0 {W},{H}"
                    text_gravity = "east"
                    text_dx = -50  # padding from right edge

                cmd += [
                    "-fill", style["panel_color"],
                    "-draw", panel_draw,
                    "-font", font,
                ]

                for item in layout["items"]:
                    key = item["key"]
                    text = {"title": title, "subtitle": subtitle, "tag": tag}.get(key, "")
                    if not text:
                        continue
                    color = item.get("color_override") or style["colors"].get(key, "white")
                    cmd += [
                        "-fill", color,
                        "-pointsize", str(item["size"]),
                        "-gravity", text_gravity,
                        "-annotate", f"+{text_dx}+{item['dy']}", text,
                    ]

                cmd.append(str(out_path))
                subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                bg_path.unlink(missing_ok=True)

                if out_path.is_file():
                    variants.append({
                        "path": str(out_path),
                        "style": style["name"],
                        "layout": layout["name"],
                        "filename": out_name,
                    })
                idx += 1

        if not variants:
            return ToolResult(success=False, error="No variants were generated")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "output_dir": str(output_dir),
                "count": len(variants),
                "variants": variants,
            },
            artifacts=[v["path"] for v in variants],
            model="pollinations/cover",
        )
