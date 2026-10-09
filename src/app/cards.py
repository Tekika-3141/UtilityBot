from io import BytesIO
from typing import Any
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field, field_validator


class CardElement(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(default=0.25, gt=0, le=1)
    height: float = Field(default=0.15, gt=0, le=1)
    rotation: float = Field(default=0, ge=-360, le=360)
    text: str = Field(default="", max_length=500)
    color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    opacity: float = Field(default=1, ge=0, le=1)
    locked: bool = False

    @field_validator("type")
    @classmethod
    def allowed_type(cls, value: str) -> str:
        if value not in {"text", "rect", "avatar", "username", "guild_name"}:
            raise ValueError("許可されていない要素です")
        return value


class CardDocument(BaseModel):
    version: int = 1
    width: int = Field(default=1200, ge=320, le=2400)
    height: int = Field(default=630, ge=180, le=1600)
    background: str = Field(default="#202225", pattern=r"^#[0-9a-fA-F]{6}$")
    elements: list[CardElement] = Field(default_factory=list, max_length=50)


def render_card(document: CardDocument, variables: dict[str, Any]) -> bytes:
    image = Image.new("RGBA", (document.width, document.height), document.background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(14, document.width // 45))
    for element in document.elements:
        x, y = int(element.x * document.width), int(element.y * document.height)
        w, h = int(element.width * document.width), int(element.height * document.height)
        fill = element.color
        if element.type == "rect":
            draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=fill)
        elif element.type in {"text", "username", "guild_name"}:
            value = element.text if element.type == "text" else variables.get(element.type, "")
            draw.text((x, y), value[:500], fill=fill, font=font)
        elif element.type == "avatar":
            size = min(w, h)
            avatar = variables.get("avatar")
            if isinstance(avatar, bytes):
                try:
                    avatar_image = Image.open(BytesIO(avatar)).convert("RGBA")
                    avatar_image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (size, size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                    image.paste(avatar_image, (x, y), mask)
                except (OSError, ValueError):
                    draw.ellipse((x, y, x + size, y + size), fill=fill)
            else:
                draw.ellipse((x, y, x + size, y + size), fill=fill)
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
