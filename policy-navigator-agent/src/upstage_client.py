import requests
from openai import OpenAI

from config import MOCK_MODE, SOLAR_MODEL, UPSTAGE_API_KEY, UPSTAGE_BASE_URL


DOCUMENT_PARSE_PATH = "/document-digitization"  # TODO: Upstage 문서에 맞춰 수정


def _with_version(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _without_version(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _strip_solar(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[:-6] if base.endswith("/solar") else base


BASE_URL = _without_version(_strip_solar(UPSTAGE_BASE_URL))
VERSIONED_BASE_URL = _with_version(BASE_URL)
SOLAR_BASE_URL = f"{VERSIONED_BASE_URL}/solar"


MOCK_SOLAR_RESPONSE = """
[판단 요약]
- 현재 프로필 기준으로 청년 주거·취업 지원 패키지 일부 항목에 해당 가능성이 높음
- 소득 기준과 거주 요건 증빙이 핵심

[선택지]
1) 월세 지원(12개월)
2) 직무교육 바우처(1회)
3) 구직활동비(6개월)

[시뮬레이션]
- 월세 지원 선택 시: 월 20만원 x 12개월 = 240만원 절감
- 구직활동비 선택 시: 월 10만원 x 6개월 = 60만원 확보

[추천 행동]
- 정부24 회원가입 및 본인인증 완료
- 주민등록등본, 소득증빙 서류 사전 발급
- 교육 바우처 과정 리스트 확인 후 1순위 선택

[추가 질문]
- 최근 3개월 소득 변동이 있나요?
- 현재 거주 형태(월세/전세/자가)는 무엇인가요?
""".strip()


MOCK_PARSED_DOC = {
    "text": "정책 문서 텍스트(파싱 결과) 예시",
    "pages": 3,
    "source": "mock",
}


def call_solar(prompt: str) -> str:
    if MOCK_MODE:
        return MOCK_SOLAR_RESPONSE

    client = OpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=SOLAR_BASE_URL,
    )
    # TODO: Upstage 문서에 맞춰 수정
    response = client.chat.completions.create(
        model=SOLAR_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
        stream=False,
    )
    return response.choices[0].message.content


def call_document_parse(pdf_path: str) -> dict:
    if MOCK_MODE:
        parsed = dict(MOCK_PARSED_DOC)
        parsed["source"] = pdf_path
        return parsed

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
    # TODO: Upstage 문서에 맞춰 수정
    with open(pdf_path, "rb") as file_handle:
        files = {"document": file_handle}
        response = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    response.raise_for_status()
    return response.json()
