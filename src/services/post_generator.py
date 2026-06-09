from dataclasses import dataclass, field
from html import escape


@dataclass(frozen=True)
class QualityButton:
    label: str
    token: str
    premium: bool = False


@dataclass(frozen=True)
class CustomButton:
    label: str
    url: str


@dataclass(frozen=True)
class GeneratedPost:
    text: str
    buttons: list[list[dict[str, str]]]


@dataclass(frozen=True)
class PostDraft:
    title: str
    description: str | None = None
    cover_file_id: str | None = None
    hidden_preview_file_id: str | None = None
    qualities: list[QualityButton] = field(default_factory=list)
    custom_buttons: list[CustomButton] = field(default_factory=list)


class PostGeneratorService:
    def __init__(self, deep_link_base: str) -> None:
        self.deep_link_base = deep_link_base

    def generate(self, draft: PostDraft) -> GeneratedPost:
        parts = [f"<b>{escape(draft.title)}</b>"]
        if draft.description:
            parts.extend(["", escape(draft.description)])
        if draft.hidden_preview_file_id:
            parts.extend(["", "<tg-spoiler>Preview is attached to the channel post.</tg-spoiler>"])

        rows: list[list[dict[str, str]]] = []
        for quality in draft.qualities:
            label = f"{quality.label} VIP" if quality.premium else quality.label
            rows.append([{"text": label, "url": self.deep_link_base + quality.token}])
        for button in draft.custom_buttons:
            rows.append([{"text": button.label, "url": button.url}])
        return GeneratedPost(text="\n".join(parts), buttons=rows)
