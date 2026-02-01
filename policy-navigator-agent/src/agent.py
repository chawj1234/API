import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from prompts import (
    build_solar_prompt,
    build_plan_prompt,
    build_question_filter_prompt,
    build_profile_extract_prompt,
    build_profile_parse_prompt,
    format_profile_structured,
)
from upstage_client import call_document_parse, call_information_extract, call_solar


# 기본 PDF 경로 (data 폴더 내) — 금융·재정·조세 정책
DEFAULT_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "finance_policy.pdf")
MAX_POLICY_TEXT_CHARS = 20000
# Plan 전용 정책 텍스트 길이 제한. None이면 전체 사용. 빈 응답 원인 파악 시 6000 등으로 줄여서 테스트.
PLAN_MAX_POLICY_CHARS: Optional[int] = None


REQUIRED_HEADERS = [
    "[자격 판단]",
    "[신청 가능 정책]",
    "[예상 혜택]",
    "[다음 단계]",
    "[확인 필요 사항]",
]

# Upstage IE API: 1레벨 property는 string/number/integer/boolean/array만 허용. object 불가.
IE_SCHEMA = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string", "description": "정책/프로그램 명칭"},
        "target_eligibility": {"type": "string", "description": "대상 및 자격 요건 요약"},
        "application_period_start": {"type": "string", "description": "신청 시작일 (YYYY-MM-DD)"},
        "application_period_end": {"type": "string", "description": "신청 종료일 (YYYY-MM-DD)"},
        "benefit": {"type": "string", "description": "혜택/지원 내용"},
        "required_documents": {
            "type": "array",
            "items": {"type": "string"},
            "description": "필요 서류 목록",
        },
        "how_to_apply": {"type": "string", "description": "신청 방법 요약"},
        "notes": {"type": "string", "description": "유의사항"},
    },
}


def _clean_terminal_output(text: str) -> str:
    """터미널 가독성: 굵은글씨(**...**) 제거."""
    s = text.strip()
    for _ in range(5):
        prev, s = s, re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
        if s == prev:
            break
    return s.strip()


def _ensure_required_headers(text: str) -> str:
    """출력에 필수 섹션 헤더가 포함되어 있는지 확인."""
    missing = [header for header in REQUIRED_HEADERS if header not in text]
    if not missing:
        return text.strip()

    lines = [text.strip()] if text.strip() else []
    for header in missing:
        lines.append(f"\n{header}\n- 내용이 생성되지 않았습니다.")
    return "\n".join(lines).strip()


def _policy_text_from_parsed_doc(parsed_doc: Dict[str, Any]) -> str:
    """Document Parse 응답을 텍스트로 변환.

    우선 content.text / content.html, 그다음 elements[] 내 paragraph/heading 등
    content.text를 모아 사용. 본문이 elements에만 있는 API 응답 구조 대응.
    """
    for key in ("html", "text", "content"):
        val = parsed_doc.get(key)
        if isinstance(val, str) and val.strip():
            return _normalize_policy_text(val)
        if isinstance(val, dict):
            for nested_key in ("text", "html"):
                nested_val = val.get(nested_key)
                if isinstance(nested_val, str) and nested_val.strip():
                    return _normalize_policy_text(nested_val)
    # content.text가 비어 있고 elements에 본문이 있는 경우
    elements = parsed_doc.get("elements") or parsed_doc.get("content", {}).get("elements")
    if isinstance(elements, list):
        parts = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            cat = el.get("category") or el.get("type") or ""
            content = el.get("content")
            if isinstance(content, dict):
                t = content.get("text") or content.get("markdown") or content.get("html")
            elif isinstance(content, str):
                t = content
            else:
                t = None
            if t and str(t).strip():
                parts.append(str(t).strip())
        if parts:
            return _normalize_policy_text(" ".join(parts))
    try:
        return _normalize_policy_text(json.dumps(parsed_doc, ensure_ascii=False))
    except Exception:
        return _normalize_policy_text(str(parsed_doc))


def _normalize_policy_text(raw_text: str) -> str:
    """HTML/잡음 제거 및 길이 제한."""
    text = raw_text
    if "<" in text and ">" in text:
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_POLICY_TEXT_CHARS]


def _get_structured_profile(profile: str) -> str:
    """
    프로필 문자열을 구조화하여 반환. Plan/질문필터에 전달.
    실패 시 원본 profile 반환.
    """
    try:
        prompt = build_profile_parse_prompt(profile=profile)
        output = call_solar(prompt, reasoning_effort=None)
        parsed = None
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            start = output.find("{")
            end = output.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(output[start : end + 1])
        if isinstance(parsed, dict) and parsed:
            structured = format_profile_structured(parsed)
            if structured:
                return structured
    except Exception:
        pass
    return profile.strip()


def _filter_questions_llm(profile: str, questions: Any) -> list:
    """LLM 기반 질문 필터링: 프로필에 이미 답이 있는 질문은 제외."""
    raw = list(questions or [])
    if not raw:
        return []

    # 질문이 dict 리스트인지 확인
    normalized = []
    for item in raw:
        if isinstance(item, dict) and (item.get("question") or item.get("field")):
            normalized.append(item)
        elif isinstance(item, str) and item.strip():
            normalized.append({"field": None, "question": item.strip()})

    if not normalized:
        return []

    try:
        prompt = build_question_filter_prompt(profile=profile, questions=normalized)
        output = call_solar(prompt, reasoning_effort=None)

        # JSON 배열 파싱 (앞뒤 설명 제거)
        parsed = None
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            start = output.find("[")
            end = output.rfind("]")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(output[start : end + 1])

        if isinstance(parsed, list) and parsed:
            filtered = [x for x in parsed if isinstance(x, dict) and (x.get("question") or x.get("field"))]
            return filtered
        if isinstance(parsed, list):
            return []
    except Exception:
        pass

    return normalized


def _parse_plan_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Solar Plan 출력에서 JSON을 추출.

    Solar Pro 3 reasoning_effort=high 시 추론 블록(<think>...</think>) 또는
    마크다운(```json ... ```)으로 감싼 JSON이 올 수 있으므로 제거 후 파싱.
    """
    if not raw_text or not raw_text.strip():
        return None
    text = raw_text.strip()
    # <think>...</think> 블록 제거 (reasoning 출력)
    if "</think>" in text:
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.DOTALL)
        text = text.strip()
    # ```json ... ``` 또는 ``` ... ``` 코드블록에서 내용만 추출
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _plan_phase(profile: str, policy_text: str, ie_extract: Optional[str]) -> Dict[str, Any]:
    """Solar Plan 단계: 조건 분석 및 질문 생성."""
    plan_text = (
        policy_text[:PLAN_MAX_POLICY_CHARS] if PLAN_MAX_POLICY_CHARS else policy_text
    )
    prompt = build_plan_prompt(profile=profile, policy_text=plan_text, ie_extract=ie_extract)
    output = call_solar(prompt, reasoning_effort="medium", max_tokens=8192)
    parsed = _parse_plan_json(output)
    
    if parsed:
        return parsed
    
    return {
        "certain_conditions": [],
        "uncertain_conditions": [],
        "questions": [],
        "action_candidates": [],
    }


def _safe_information_extract(pdf_path: str) -> Optional[str]:
    """Information Extraction 결과를 안전하게 반환. PDF 파일 경로를 넘긴다."""
    try:
        result = call_information_extract(document_path=pdf_path, schema=IE_SCHEMA)
    except Exception:
        return None

    try:
        return json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _append_profile_field(profile: str, field_name: str, value: str) -> str:
    """프로필에 새 필드 추가."""
    updated_profile = profile.strip()
    if f"{field_name}:" in updated_profile:
        return updated_profile
    if updated_profile:
        return f"{updated_profile}/ {field_name}: {value}"
    return f"{field_name}: {value}"


def _update_profile_from_message_llm(
    profile: str,
    user_message: str,
    question_text: str = "",
    field_name: Optional[str] = None,
) -> str:
    """LLM 기반: 질문 맥락 + 사용자 답변으로 프로필 정보 추출 및 병합."""
    if not user_message or not user_message.strip():
        return profile.strip()

    try:
        prompt = build_profile_extract_prompt(
            user_message=user_message.strip(),
            question_text=question_text or "",
            field_name=field_name or "",
        )
        output = call_solar(prompt, reasoning_effort=None)

        parsed = None
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            start = output.find("{")
            end = output.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(output[start : end + 1])

        updated = profile.strip()
        if isinstance(parsed, dict) and parsed:
            for fn, value in parsed.items():
                if fn and value and isinstance(value, str):
                    updated = _append_profile_field(updated, fn, value.strip())
        else:
            if field_name:
                updated = _append_profile_field(updated, field_name, user_message.strip())
        return updated
    except Exception:
        if field_name:
            return _append_profile_field(profile.strip(), field_name, user_message.strip())
        return profile.strip()


def run(profile: str, pdf_path: Optional[str] = None) -> str:
    """정책 에이전트 실행 (항상 대화형).

    Args:
        profile: 사용자 프로필 문자열
        pdf_path: 정책 PDF 경로 (없으면 기본 PDF 사용)

    Returns:
        최종 상담 결과 문자열
    """
    # PDF 경로 설정 (기본값: finance_policy.pdf)
    actual_pdf_path = pdf_path or DEFAULT_PDF_PATH
    
    if not os.path.exists(actual_pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {actual_pdf_path}")

    print(f"\n📄 PDF 파싱 및 정보 추출 중 : {actual_pdf_path}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_parse = executor.submit(call_document_parse, actual_pdf_path)
        future_ie = executor.submit(_safe_information_extract, actual_pdf_path)
        parsed_doc = future_parse.result()
        ie_extract = future_ie.result()
    policy_text = _policy_text_from_parsed_doc(parsed_doc)
    print("✅ PDF 파싱 완료\n")

    profile_for_prompts = _get_structured_profile(profile)

    # Plan 단계 (1차 분석: 조건 판단·질문 생성)
    print("🔍 Plan (1차 분석): 조건 판단·질문 생성 중...")
    plan_result = _plan_phase(profile=profile_for_prompts, policy_text=policy_text, ie_extract=ie_extract)
    c, u, q, a = (
        plan_result.get("certain_conditions", []),
        plan_result.get("uncertain_conditions", []),
        plan_result.get("questions", []),
        plan_result.get("action_candidates", []),
    )
    print("✅ 분석 완료\n")

    answered_fields: Dict[str, str] = {}

    # 대화형 질문/응답 (항상 실행)
    questions = _filter_questions_llm(profile_for_prompts, plan_result.get("questions", []))
    if questions:
        print("━" * 50)
        print("📋 추가 정보가 필요합니다:")
        print("━" * 50)
        
        for item in questions:
            if isinstance(item, dict):
                field_name = item.get("field")
                question_text = item.get("question") or field_name
            else:
                field_name = None
                question_text = str(item)

            if not question_text:
                continue

            answer = input(f"\n❓ {question_text}\n👉 ").strip()
            if not answer:
                continue

            profile = _update_profile_from_message_llm(
                profile, answer,
                question_text=question_text or "",
                field_name=field_name or "",
            )
            if field_name:
                answered_fields[field_name] = answer

        # 재평가
        print("\n🔄 Plan 재분석 중...")
        profile_for_prompts = _get_structured_profile(profile)
        plan_result = _plan_phase(profile=profile_for_prompts, policy_text=policy_text, ie_extract=ie_extract)
        print("✅ Plan 재분석 완료\n")

    # Final 단계
    print("📝 최종 상담 결과 생성 중...")
    plan_json = json.dumps(plan_result, ensure_ascii=False)
    answered_json = json.dumps(answered_fields, ensure_ascii=False) if answered_fields else None
    prompt = build_solar_prompt(
        profile=profile_for_prompts,
        policy_text=policy_text,
        agent_plan=plan_json,
        answered_fields=answered_json,
        ie_extract=ie_extract,
    )
    output = call_solar(prompt, reasoning_effort="medium")
    print("✅ 완료\n")

    print("━" * 50)
    print("📌 최종 상담 결과")
    print("━" * 50)

    return _ensure_required_headers(_clean_terminal_output(output))
