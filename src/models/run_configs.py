import json
from dataclasses import dataclass, field


@dataclass
class RunConfigs:
    background: str = ""
    promotion_url: str = ""
    process_video: bool = True
    replace_audio: bool = False
    remove_tags: list[str] = field(default_factory=list)
    add_tags: list[str] = field(default_factory=list)
    default_content: str = ""
    translate_code: str = ""

    @classmethod
    def from_json(cls, json_str: str) -> "RunConfigs":
        if not json_str or not json_str.strip():
            return cls()
        data = json.loads(json_str)
        return cls(
            background=data.get("background", ""),
            promotion_url=data.get("promotionURL", ""),
            process_video=data.get("processVideo", True),
            replace_audio=data.get("replaceAudio", False),
            remove_tags=[t.strip() for t in data.get("removeTags", "").split(",") if t.strip()],
            add_tags=[t.strip() for t in data.get("addTags", "").split(",") if t.strip()],
            default_content=data.get("defaultContent", ""),
            translate_code=data.get("translateCode", ""),
        )
