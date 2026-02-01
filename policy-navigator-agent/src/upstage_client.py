import base64
import json
import requests
from openai import OpenAI

from config import SOLAR_MODEL, UPSTAGE_API_KEY, UPSTAGE_BASE_URL


DOCUMENT_PARSE_PATH = "/document-digitization"
INFORMATION_EXTRACT_PATH = "/information-extraction"


def _ensure_v1(base_url: str) -> str:
    """Upstage API는 /v1 경로가 필요함."""
    trimmed = base_url.rstrip("/")
    return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"


VERSIONED_BASE_URL = _ensure_v1(UPSTAGE_BASE_URL)
SOLAR_BASE_URL = VERSIONED_BASE_URL


def call_solar(
    prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 16384,
    reasoning_effort: str | None = None,
) -> str:
    """Solar 모델을 호출하여 응답을 반환.

    reasoning_effort: Solar Pro 2는 기본 꺼짐, "high"로 활성화.
                      Solar Pro 3는 high(60%)/medium(30%)/low(꺼짐).
    """
    client = OpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=SOLAR_BASE_URL,
    )
    kwargs: dict = {
        "model": SOLAR_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    response = client.chat.completions.create(**kwargs)
    choice = response.choices[0] if response.choices else None
    content = choice.message.content if choice and choice.message else None
    return content if content is not None else ""


def call_document_parse(pdf_path: str) -> dict:
    """Document Parse API를 호출하여 PDF를 파싱."""
    url = f"{VERSIONED_BASE_URL}{DOCUMENT_PARSE_PATH}"
    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
    data = {
        "model": "document-parse-nightly",
        "mode": "auto",
        "ocr": "auto",
        "chart_recognition": True,
        "coordinates": True,
        "output_formats": '["html"]',
        "base64_encoding": '["figure"]',
    }
    with open(pdf_path, "rb") as file_handle:
        files = {"document": file_handle}
        response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
    if not response.ok:
        msg = f"Document Parse API 오류 ({response.status_code}). "
        if response.status_code == 500:
            msg += "Upstage 서버 일시 오류입니다. 잠시 후 다시 시도하세요."
        elif response.status_code == 401:
            msg += "API 키를 확인하거나 결제/크레딧 상태를 확인하세요."
        else:
            msg += response.text[:200] if response.text else ""
        raise RuntimeError(msg)
    return response.json()


def call_information_extract(document_path: str, schema: dict) -> dict:
    """Information Extraction API 호출. 문서(PDF/이미지)를 base64로 전달."""
    with open(document_path, "rb") as f:
        raw = f.read()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    # Upstage IE API는 문서를 image_url 형태의 base64로 받음 (PDF는 application/pdf)
    mime = "application/pdf" if document_path.lower().endswith(".pdf") else "image/png"
    data_url = f"data:{mime};base64,{b64}"

    client = OpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=f"{VERSIONED_BASE_URL}{INFORMATION_EXTRACT_PATH}",
    )
    response = client.chat.completions.create(
        model="information-extract",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "policy_schema",
                "schema": schema,
            },
        },
        timeout=120,
    )
    content = response.choices[0].message.content
    try:
        return json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError:
        return {}
