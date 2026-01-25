import json
import os
import re
from typing import Optional, Dict, Any

from prompts import build_solar_prompt, build_plan_prompt
from upstage_client import call_document_parse, call_information_extract, call_solar


# 기본 PDF 경로 (data 폴더 내)
DEFAULT_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_policy.pdf")
MAX_POLICY_TEXT_CHARS = 20000


REQUIRED_HEADERS = [
    "[자격 판단]",
    "[신청 가능 정책]",
    "[예상 혜택]",
    "[다음 단계]",
    "[확인 필요 사항]",
]

IE_SCHEMA = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string", "description": "정책/프로그램 명칭"},
        "target_eligibility": {"type": "string", "description": "대상 및 자격 요건 요약"},
        "application_period": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "신청 시작일 (YYYY-MM-DD)"},
                "end": {"type": "string", "description": "신청 종료일 (YYYY-MM-DD)"},
            },
            "description": "신청 기간",
        },
        "benefit": {"type": "string", "description": "혜택/지원 내용"},
        "required_documents": {
            "type": "array",
            "items": {"type": "string"},
            "description": "필요 서류 목록",
        },
        "how_to_apply": {"type": "string", "description": "신청 방법 요약"},
        "notes": {"type": "string", "description": "유의사항"},
    },
    "required": ["program_name", "target_eligibility", "benefit"],
}


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
    """Document Parse 응답을 텍스트로 변환."""
    for key in ("html", "text", "content"):
        val = parsed_doc.get(key)
        if isinstance(val, str) and val.strip():
            return _normalize_policy_text(val)
        if isinstance(val, dict):
            for nested_key in ("html", "text"):
                nested_val = val.get(nested_key)
                if isinstance(nested_val, str) and nested_val.strip():
                    return _normalize_policy_text(nested_val)

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


def _extract_profile_facts(profile: str) -> Dict[str, Any]:
    """프로필 문자열에서 확정 사실을 최소한으로 추출."""
    facts: Dict[str, Any] = {
        "marital_status": None,
        "has_children": None,
        "is_metropolitan": None,
        "location": None,
        "is_student": None,
    }

    normalized = profile.strip()

    if "미혼" in normalized:
        facts["marital_status"] = "미혼"
        if "자녀" not in normalized:
            facts["has_children"] = False
    elif "기혼" in normalized:
        facts["marital_status"] = "기혼"

    if any(token in normalized for token in ["자녀 없음", "무자녀", "자녀0"]):
        facts["has_children"] = False
    elif "자녀" in normalized:
        facts["has_children"] = True

    for location in ["수도권", "서울", "경기", "인천", "부산", "대구"]:
        if location in normalized:
            facts["location"] = location
            break

    if facts["location"] in {"수도권", "서울", "경기", "인천"}:
        facts["is_metropolitan"] = True
    elif facts["location"]:
        facts["is_metropolitan"] = False

    if any(token in normalized for token in ["대학생", "재학", "대학(원)"]):
        facts["is_student"] = True

    return facts


def _should_skip_question(question_text: str, field_name: Optional[str], profile: str) -> bool:
    """프로필과 모순되거나 이미 제공된 정보는 질문에서 제외."""
    if field_name and f"{field_name}:" in profile:
        return True

    facts = _extract_profile_facts(profile)
    text = question_text.strip()

    if facts["has_children"] is False and "자녀" in text:
        return True

    if facts["marital_status"] and facts["marital_status"] in text:
        return True

    if facts["is_metropolitan"] is True and any(
        token in text for token in ["농어촌", "인구감소지역", "비수도권", "지방"]
    ):
        return True

    if facts["is_metropolitan"] is True and "수도권" in text:
        return True

    if facts["is_student"] is True and any(token in text for token in ["재학", "대학", "대학(원)"]):
        return True

    return False


def _filter_questions(profile: str, questions: Any) -> list:
    """질문 목록에서 중복/모순 질문을 제거."""
    filtered = []
    for item in questions or []:
        if isinstance(item, dict):
            field_name = item.get("field")
            question_text = item.get("question") or field_name or ""
        else:
            field_name = None
            question_text = str(item)

        if not question_text:
            continue

        if _should_skip_question(question_text, field_name, profile):
            continue

        filtered.append(item)

    return filtered


def _parse_plan_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Solar Plan 출력에서 JSON을 추출."""
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(raw_text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _plan_phase(profile: str, policy_text: str, ie_extract: Optional[str]) -> Dict[str, Any]:
    """Solar Plan 단계: 조건 분석 및 질문 생성."""
    prompt = build_plan_prompt(profile=profile, policy_text=policy_text, ie_extract=ie_extract)
    output = call_solar(prompt)
    parsed = _parse_plan_json(output)
    
    if parsed:
        return parsed
    
    # JSON 파싱 실패 시 기본값 반환
    return {
        "certain_conditions": [],
        "uncertain_conditions": [],
        "questions": [],
        "action_candidates": [],
    }


def _safe_information_extract(policy_text: str) -> Optional[str]:
    """Information Extraction 결과를 안전하게 반환."""
    try:
        result = call_information_extract(text=policy_text, schema=IE_SCHEMA)
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


def _update_profile_from_message(profile: str, user_message: str) -> str:
    """사용자 메시지에서 프로필 정보 추출 및 업데이트."""
    updated_profile = profile.strip()

    age_match = re.search(r"(\d{2})\s*(세|살)", user_message)
    if age_match:
        updated_profile = _append_profile_field(updated_profile, "나이", f"{age_match.group(1)}세")

    income_match = re.search(r"월\s*(\d{2,4})\s*(만|만원)?", user_message)
    if income_match:
        updated_profile = _append_profile_field(updated_profile, "소득", f"월{income_match.group(1)}만원")

    if "미혼" in user_message:
        updated_profile = _append_profile_field(updated_profile, "혼인", "미혼")
    elif "기혼" in user_message:
        updated_profile = _append_profile_field(updated_profile, "혼인", "기혼")

    for location in ["수도권", "서울", "경기", "인천", "부산", "대구"]:
        if location in user_message:
            updated_profile = _append_profile_field(updated_profile, "거주지", location)
            break

    for job in ["중소기업", "대학생", "구직", "프리랜서", "직장인"]:
        if job in user_message:
            updated_profile = _append_profile_field(updated_profile, "직업", job)
            break

    return updated_profile


def run(profile: str, pdf_path: Optional[str] = None) -> str:
    """정책 에이전트 실행 (항상 대화형).

    Args:
        profile: 사용자 프로필 문자열
        pdf_path: 정책 PDF 경로 (없으면 기본 PDF 사용)

    Returns:
        최종 상담 결과 문자열
    """
    # PDF 경로 설정 (기본값: sample_policy.pdf)
    actual_pdf_path = pdf_path or DEFAULT_PDF_PATH
    
    if not os.path.exists(actual_pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {actual_pdf_path}")

    print(f"\n📄 PDF 파싱 중: {actual_pdf_path}")
    parsed_doc = call_document_parse(actual_pdf_path)
    policy_text = _policy_text_from_parsed_doc(parsed_doc)
    ie_extract = _safe_information_extract(policy_text)
    print("✅ PDF 파싱 완료\n")

    # Plan 단계
    print("🔍 정책 분석 중...")
    plan_result = _plan_phase(profile=profile, policy_text=policy_text, ie_extract=ie_extract)
    print("✅ 분석 완료\n")

    answered_fields: Dict[str, str] = {}

    # 대화형 질문/응답 (항상 실행)
    questions = _filter_questions(profile, plan_result.get("questions", []))
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

            if field_name:
                profile = _append_profile_field(profile, field_name, answer)
                answered_fields[field_name] = answer
            profile = _update_profile_from_message(profile, answer)

        # 재평가
        print("\n🔄 정보를 반영하여 재분석 중...")
        plan_result = _plan_phase(profile=profile, policy_text=policy_text, ie_extract=ie_extract)
        print("✅ 재분석 완료\n")

    # Final 단계
    print("📝 최종 상담 결과 생성 중...")
    plan_json = json.dumps(plan_result, ensure_ascii=False)
    answered_json = json.dumps(answered_fields, ensure_ascii=False) if answered_fields else None
    prompt = build_solar_prompt(
        profile=profile,
        policy_text=policy_text,
        agent_plan=plan_json,
        answered_fields=answered_json,
        ie_extract=ie_extract,
    )
    output = call_solar(prompt)
    print("✅ 완료\n")

    print("━" * 50)
    print("📌 최종 상담 결과")
    print("━" * 50)

    return _ensure_required_headers(output)
