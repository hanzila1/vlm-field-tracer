"""
VLM interface — prompts and Gemini API call wrapper.
"""

import io
from PIL import Image

from google import genai
from google.genai import types


MODEL_NAME = "models/gemini-3.1-flash-image-preview"


PROMPT_LINES = """TASK: AGRICULTURAL FIELD BOUNDARY LINE EXTRACTION

Analyze this satellite/aerial image. Draw ONLY the boundary lines between agricultural fields.

OUTPUT FORMAT — ABSOLUTE RULES:
• Pure WHITE background (#FFFFFF) — every pixel not a line must be white
• Field boundary lines in SOLID BLACK (#000000), 2px wide, lines only
• NO fills, NO blobs, NO shading, NO dots, NO colors anywhere
• Urban/village/building areas: leave completely WHITE — do not draw anything there
• Water/roads: leave completely WHITE — do not draw anything there

DRAW ONLY:
• Thin black lines along the edges between agricultural field parcels
• Lines must be continuous, connected at junctions, straight where boundary is straight

DO NOT DRAW UNDER ANY CIRCUMSTANCES:
• Do NOT fill or shade urban areas, villages, or buildings — leave WHITE
• Do NOT place dots, blobs, or marks on non-agricultural areas — leave WHITE
• Do NOT draw building outlines or urban textures
• Do NOT draw roads, paths, or any non-field feature
• Do NOT fill field interiors
• Do NOT add any labels or text

THE OUTPUT MUST BE: only thin black lines on a completely white background.
If an area is urban/village/water/road — it must be pure white, nothing drawn there.

Generate the agricultural field boundary line map now."""


PROMPT_POINTS = """TASK: URBAN AREA CENTER POINT MARKER

Analyze this satellite/aerial image. Place ONE black dot at the CENTER of each urban/village/built-up area ONLY.

OUTPUT FORMAT — ABSOLUTE RULES:
• Pure WHITE background (#FFFFFF) — the entire image must be white
• ONE SOLID BLACK FILLED CIRCLE per urban area, radius ~10px
• Nothing else — no lines, no fills, no colors, no shading, no text
• The output must look like: white image with a few black dots on it

WHAT IS AN URBAN AREA:
• Villages, towns, residential clusters
• Dense building groups
• Built-up areas with houses and structures

PLACE ONE DOT:
• Exactly at the geographic CENTER of each distinct urban/village cluster
• ONE dot per cluster — not one per building, not one per street
• The dot marks the center/centroid of the whole urban area

DO NOT PLACE DOTS ON:
• Agricultural fields — no dots there
• Roads or paths — no dots there
• Water bodies — no dots there
• Vegetation — no dots there
• Empty land — no dots there

DO NOT DRAW:
• No outlines of any area
• No filled polygons or shading
• No lines of any kind
• No colors — only black dots on white

THE OUTPUT MUST BE: pure white image with only a small number of black filled circles marking urban area centers.

Generate the urban area center point map now."""


def call_vlm(client, image, prompt):
    buf = io.BytesIO()
    img = image.convert('RGB') if image.mode != 'RGB' else image
    img.save(buf, format='JPEG', quality=95)
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return Image.open(io.BytesIO(part.inline_data.data)).convert('RGB')
    except Exception as e:
        print(f"   ⚠️  API error: {e}")
    return None
