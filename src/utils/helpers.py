import hashlib
import re
from src.models.run_configs import RunConfigs

_EMOJI_RE = re.compile(
    "[\U00010000-\U0010FFFF"
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "☀-⛿✀-➿]+",
    flags=re.UNICODE,
)


def remove_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def clean_text(text: str) -> str:
    """Loại bỏ ký tự lỗi  (\ufffd), emoji và các ký tự lạ gây lỗi Facebook"""
    if not text:
        return ""
    # 1. Xóa ký tự replacement character \ufffd (lỗi hiển thị )
    text = text.replace("\ufffd", "")
    
    # 2. Xóa emoji bằng regex đã có
    text = remove_emoji(text)
    
    # 3. Lọc bỏ các ký tự không in được (control characters) trừ xuống dòng
    text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
    
    return text.strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_description(content: str, configs: RunConfigs) -> str:
    if configs.default_content:
        # Vẫn chạy qua clean_text để đảm bảo không có ký tự lỗi từ sheet
        return clean_text(configs.default_content)

    result = content
    for tag in configs.remove_tags:
        result = result.replace(f"#{tag}", "").replace(tag, "")

    existing_tags = set(re.findall(r"#(\w+)", result))
    new_tags = " ".join(f"#{t}" for t in configs.add_tags if t not in existing_tags)
    if new_tags:
        result = f"{result.strip()} {new_tags}"

    if configs.promotion_url:
        result = f"{configs.promotion_url}\n{result}"

    # Làm sạch toàn bộ emoji/ký tự lỗi trước khi trả về
    return clean_text(result)
