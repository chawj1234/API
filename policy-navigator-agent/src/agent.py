import json
from typing import Optional, Dict, Any

from prompts import SAMPLE_POLICY_TEXT, build_solar_prompt
from upstage_client import call_document_parse, call_solar


REQUIRED_HEADERS = [
    "[판단 요약]",
    "[선택지]",
    "[시뮬레이션]",
    "[추천 행동]",
    "[추가 질문]",
]


def _ensure_required_headers(text: str) -> str:
    """Ensure the final output always contains the required section headers."""
    missing = [header for header in REQUIRED_HEADERS if header not in text]
    if not missing:
        return text.strip()

    lines = [text.strip()] if text.strip() else []
    for header in missing:
        lines.append(f"\n{header}\n- 내용이 생성되지 않았습니다. 입력/프롬프트를 확인해주세요.")
    return "\n".join(lines).strip()


def _policy_text_from_parsed_doc(parsed_doc: Dict[str, Any]) -> str:
    """Best-effort conversion of Document Parse response to a text blob for Solar."""
    # Upstage Document Parse commonly returns HTML when output_formats includes ["html"].
    for key in ("html", "text", "content"):
        val = parsed_doc.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict):
            for nested_key in ("html", "text"):
                nested_val = val.get(nested_key)
                if isinstance(nested_val, str) and nested_val.strip():
                    return nested_val

    # Sometimes responses include nested structures; fall back to JSON.
    try:
        return json.dumps(parsed_doc, ensure_ascii=False)[:20000]
    except Exception:
        return str(parsed_doc)[:20000]


def run(profile: str, pdf_path: Optional[str] = None) -> str:
    """Run the policy agent.

    - If `pdf_path` is provided: uses Document Parse to structure the PDF.
    - If not provided: uses embedded SAMPLE_POLICY_TEXT.
    - Information Extract는 사용하지 않습니다.
    """

    parsed_doc: Dict[str, Any]
    if pdf_path:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        parsed_doc = call_document_parse(pdf_path)
        policy_text = _policy_text_from_parsed_doc(parsed_doc)
    else:
        parsed_doc = {"source": "embedded", "text": SAMPLE_POLICY_TEXT}
        policy_text = SAMPLE_POLICY_TEXT

    prompt = build_solar_prompt(profile=profile, policy_text=policy_text)
    output = call_solar(prompt)

    return _ensure_required_headers(output)
