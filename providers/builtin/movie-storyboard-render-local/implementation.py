from __future__ import annotations

import hashlib
import re
from html import escape

from vss_providers.contracts import GeneratedMedia, StoryboardRenderRequest


WIDTH, HEIGHT = 1200, 1500


def _lines(value: object, limit: int = 88) -> list[str]:
    text = " ".join(str(value).split())
    text = re.sub(r"https?://\S+", "[external URL omitted]", text, flags=re.IGNORECASE)
    words, lines, current = text.split(" "), [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3] or ["Not specified by validated upstream artifacts"]


def _text_block(label: str, value: object, x: int, y: int) -> tuple[list[str], int]:
    rows = [f'<text x="{x}" y="{y}" class="label">{escape(label)}:</text>']
    y += 22
    for line in _lines(value):
        rows.append(f'<text x="{x}" y="{y}" class="body">{escape(line, quote=True)}</text>')
        y += 19
    return rows, y + 5


class LocalDeterministicStoryboardSvgProvider:
    def render(self, request: StoryboardRenderRequest) -> GeneratedMedia:
        if type(request) is not StoryboardRenderRequest or len(request.frames) != 3:
            raise ValueError("exactly three admitted frames are required")
        rows = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
            '<style>.title{font:700 24px sans-serif}.head{font:700 17px sans-serif}.label{font:700 13px sans-serif}.body{font:12px sans-serif}.bind{font:10px monospace}.panel{fill:#faf8f2;stroke:#222;stroke-width:2}.placeholder{fill:#e9e6dc;stroke:#555;stroke-width:1}.line{stroke:#555;stroke-width:2}</style>',
            '<rect width="1200" height="1500" fill="#f1efe8"/>',
            '<text x="40" y="42" class="title">VSS deterministic storyboard review sheet</text>',
            f'<text x="40" y="65" class="bind">storyboard {escape(request.storyboard_specification_digest)}</text>',
            '<text x="40" y="84" class="body">Development review media — schematic, not a production asset or final selection.</text>',
        ]
        for index, frame in enumerate(request.frames, 1):
            top = 105 + (index - 1) * 455
            rows.extend([
                f'<rect x="30" y="{top}" width="1140" height="430" rx="8" class="panel"/>',
                f'<text x="50" y="{top + 28}" class="head">Frame {index} — {escape(str(frame["frame_id"]), quote=True)}</text>',
                f'<rect x="50" y="{top + 45}" width="410" height="245" class="placeholder"/>',
                f'<line x1="70" y1="{top + 265}" x2="440" y2="{top + 70}" class="line"/>',
                f'<circle cx="255" cy="{top + 165}" r="42" fill="none" class="line"/>',
                f'<text x="152" y="{top + 310}" class="body">schematic placeholder — no pictorial generation</text>',
            ])
            y = top + 55
            camera = frame["camera"]
            fields = (
                ("Subject", frame["subject_focus"]), ("Action", frame["action"]),
                ("Environment", frame["environment"]), ("Time / lighting", frame["time_and_lighting"]),
                ("Framing", camera["framing_and_shot_scale"]),
                ("Camera", "; ".join(str(camera[k]) for k in ("angle", "elevation", "movement", "composition"))),
                ("Visual style", frame["visual_style"]),
            )
            for label, value in fields:
                block, y = _text_block(label, value, 485, y)
                rows.extend(block)
            assumptions = "; ".join(frame["assumptions"]) or "None beyond validated source qualifications"
            unknowns = "; ".join(frame["explicit_unknowns"])
            block, y2 = _text_block("Assumptions", assumptions, 50, top + 342); rows.extend(block)
            block, _ = _text_block("Explicit unknowns", unknowns, 485, min(y, top + 342)); rows.extend(block)
            rows.append(f'<text x="50" y="{top + 417}" class="bind">frame digest {escape(str(frame["frame_specification_digest"]))}</text>')
        rows.append('</svg>')
        content = ("\n".join(rows) + "\n").encode("utf-8")
        return GeneratedMedia("image/svg+xml", content, WIDTH, HEIGHT, hashlib.sha256(content).hexdigest())


def create_provider() -> LocalDeterministicStoryboardSvgProvider:
    return LocalDeterministicStoryboardSvgProvider()
