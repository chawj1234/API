import json
import os
import re
from typing import Optional, Dict, Any

from prompts import build_solar_prompt, build_plan_prompt
from upstage_client import call_document_parse, call_solar


# 기본 PDF 경로 (data 폴더 내)
DEFAULT_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_policy.pdf")


REQUIRED_HEADERS = [
    "[자격 판단]",
    "[신청 가능 정책]",
    "[예상 혜택]",
    "[다음 단계]",
    "[확인 필요 사항]",
]


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
            return val
        if isinstance(val, dict):
            for nested_key in ("html", "text"):
                nested_val = val.get(nested_key)
                if isinstance(nested_val, str) and nested_val.strip():
                    return nested_val

    try:
        return json.dumps(parsed_doc, ensure_ascii=False)[:20000]
    except Exception:
        return str(parsed_doc)[:20000]


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


def _plan_phase(profile: str, policy_text: str) -> Dict[str, Any]:
    """Solar Plan 단계: 조건 분석 및 질문 생성."""
    prompt = build_plan_prompt(profile=profile, policy_text=policy_text)
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
    print("✅ PDF 파싱 완료\n")

    # Plan 단계
    print("🔍 정책 분석 중...")
    plan_result = _plan_phase(profile=profile, policy_text=policy_text)
    print("✅ 분석 완료\n")

    answered_fields: Dict[str, str] = {}

    # 대화형 질문/응답 (항상 실행)
    questions = plan_result.get("questions", [])
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
        plan_result = _plan_phase(profile=profile, policy_text=policy_text)
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
    )
    output = call_solar(prompt)
    print("✅ 완료\n")

    print("━" * 50)
    print("📌 최종 상담 결과")
    print("━" * 50)

    return _ensure_required_headers(output)
