"""Solar Pro 2 기반 프롬프트 템플릿 모듈

Solar Pro 2 Prompting Handbook의 베스트 프랙티스를 따릅니다:
- Role → Instructions → Constraints → Format → Query 구조
- JSON 출력: "Return ONLY the JSON object" 명시
- 중요 제약: CRITICAL, MUST, NEVER 등 대문자 강조
- 셀프 검증: VERIFICATION CHECKLIST 추가
"""

import json
from typing import Optional


def build_profile_parse_prompt(profile: str) -> str:
    """프로필 문자열을 JSON 객체로 파싱하는 프롬프트 생성.
    
    Args:
        profile: 슬래시 구분 프로필 문자열 (예: "29세/수도권/중소기업/월250/미혼")
    
    Returns:
        Solar에 전달할 프롬프트 문자열
    """
    return f"""# Role
당신은 사용자 프로필 문자열을 구조화된 데이터로 변환하는 전문가입니다.

# Instructions
주어진 프로필 문자열을 분석하여 JSON 객체로 변환하세요.
- 슬래시(/)로 구분된 각 항목을 적절한 필드로 매핑
- 나이, 지역, 직업/상태, 월소득, 혼인/가족 정보 추출
- 각 필드는 한국어 키로 표현

# Constraints
- MUST return ONLY valid JSON object
- NEVER add explanations, markdown, or code blocks
- 빈 필드는 빈 문자열("")로 표시
- 추가 정보가 있으면 적절한 필드명으로 추가

# Format
{{
  "나이": "29세",
  "지역": "수도권",
  "직업": "중소기업",
  "월소득": "월250",
  "혼인상태": "미혼"
}}

# Query
프로필: {profile}

위 프로필을 분석하여 JSON 객체로 변환하세요."""


def format_profile_structured(parsed: dict) -> str:
    """파싱된 프로필 dict를 한 줄 문자열로 포맷.
    
    Args:
        parsed: build_profile_parse_prompt 결과로 파싱된 dict
    
    Returns:
        "나이: 29세, 지역: 수도권, ..." 형태의 문자열
    """
    if not parsed or not isinstance(parsed, dict):
        return ""
    
    parts = []
    for key, value in parsed.items():
        if value and str(value).strip():
            parts.append(f"{key}: {value}")
    
    return ", ".join(parts) if parts else ""


def build_plan_prompt(profile: str, policy_text: str, ie_extract: Optional[str]) -> str:
    """정책 분석 Plan 단계 프롬프트 생성.
    
    Args:
        profile: 구조화된 프로필 문자열
        policy_text: Document Parse로 추출한 정책 본문
        ie_extract: Information Extraction 결과 (선택)
    
    Returns:
        Solar에 전달할 프롬프트 문자열
    """
    ie_section = ""
    if ie_extract:
        ie_section = f"""
## 추출된 핵심 정보 (참고용)
{ie_extract}
"""
    
    return f"""# Role
당신은 정부 정책 문서를 분석하여 개인 맞춤형 자격 조건과 필요 질문을 도출하는 정책 분석 전문가입니다.

# Instructions
사용자 프로필과 정책 본문을 비교 분석하여 다음을 도출하세요:

1. **확실한 조건 (certain_conditions)**: 프로필로 명확히 판단 가능한 자격 조건
2. **불확실한 조건 (uncertain_conditions)**: 프로필만으로는 판단하기 어려운 조건
3. **질문 (questions)**: uncertain_conditions를 해소하기 위해 필요한 질문 목록
4. **행동 후보 (action_candidates)**: 신청 가능하거나 검토가 필요한 정책 목록

## 질문 생성 원칙 (CRITICAL)
- **certain_conditions에 이미 결론 낸 내용은 절대 questions에 넣지 말 것**
  - 예: certain에 "자녀 없음"이면 "자녀 있나요?" 질문 금지
  - 예: certain에 "월소득 0으로 신용카드 혜택 불가"면 "신용카드 사용 여부" 질문 금지
- **프로필에 이미 답이 있는 내용은 질문하지 않음**
- **질문은 한 문장으로 짧고 간결하게**
  - 정책명, 혜택 설명 등을 질문에 포함하지 말 것
  - 바람직: "자녀가 있나요?", "신용카드를 사용하고 있나요?"
  - 비바람직: "보육수당 비과세 한도 확대를 적용받으려면 자녀가 있나요?"
- **연관 질문의 논리적 순서**
  - 선행 질문에서 "아니오"가 확정되면 후속 질문 생성 금지
  - 예: "자녀 있나요?" → "아니오"면 "자녀 만 9세 미만인가요?"는 의미 없음 → 생성 금지
  - 선행 질문에 "예"일 때만 의미 있는 후속 질문만 포함

# Constraints
- CRITICAL: Return ONLY valid JSON object
- NEVER add markdown code blocks (```json) or explanations
- questions 배열: 각 항목은 {{"field": "필드명", "question": "질문 전문"}} 구조 필수
- question 필드: 한 문장으로 짧게, 정책명/혜택 설명 포함 금지
- 정책 본문에 근거 없는 내용 생성 금지
- 모든 배열 필드는 반드시 존재해야 함 (빈 배열이라도 [] 표시)

# Format
{{
  "certain_conditions": ["조건1: 설명", "조건2: 설명"],
  "uncertain_conditions": ["불확실 조건1: 이유"],
  "questions": [
    {{"field": "주식거래여부", "question": "주식 거래 경험이 있나요?"}},
    {{"field": "배당소득여부", "question": "배당소득이 있나요?"}}
  ],
  "action_candidates": ["정책A 신청 가능", "정책B 검토 필요"]
}}

# VERIFICATION CHECKLIST
응답 전 반드시 확인:
1. certain_conditions에 있는 내용과 questions가 겹치지 않는가?
2. 각 question이 간결하며, 정책명/혜택 설명이 포함되지 않았는가?
3. 연관 질문 중 선행 "아니오" 시 의미 없는 후속 질문은 제외했는가?
4. JSON 구조가 위 Format과 정확히 일치하는가?
5. questions 배열의 각 항목에 field와 question이 모두 있는가?

# Context
## 사용자 프로필
{profile}

## 정책 문서
{policy_text[:8000]}
{ie_section}

# Query
위 프로필과 정책을 종합 분석하여 JSON을 생성하세요. 코드 블록 없이 JSON만 출력하세요."""


def build_question_filter_prompt(profile: str, questions: list) -> str:
    """프로필로 답할 수 있는 질문을 필터링하는 프롬프트 생성.
    
    Args:
        profile: 구조화된 프로필 문자열
        questions: 필터링할 질문 목록 (dict 배열)
    
    Returns:
        Solar에 전달할 프롬프트 문자열
    """
    questions_json = json.dumps(questions, ensure_ascii=False, indent=2)
    
    return f"""# Role
당신은 사용자 프로필을 분석하여 불필요한 질문을 걸러내는 전문가입니다.

# Instructions
프로필에 **명시적으로** 답이 적힌 질문만 제외하고, 나머지 질문은 그대로 반환하세요.

## 판단 기준 (CRITICAL)
- **제외**: 프로필에 해당 정보가 **직접·명시적으로** 적혀 있을 때만 제외
  - 예: 프로필에 "자녀: 2명" 적혀 있으면 "자녀 있나요?" 제외
- **제외 금지**: 유추·추측으로 제외하지 말 것
  - 예: "미혼"만 있다고 "자녀 없음"으로 추측해서 제외 금지
  - 예: "월0"만 있다고 "신용카드/보육수당 불필요"로 추측해서 제외 금지
- 프로필 형식: "나이/지역/직업/월소득/혼인상태" 등 → 자녀, 웹툰, 신용카드 등은 보통 없음 → 이 질문들은 유지

# Constraints
- MUST return ONLY a JSON array
- 각 항목은 원본 질문 객체 구조 유지 (field, question 포함)
- NEVER add explanations or markdown
- 모든 질문을 제외해야 한다면 빈 배열 [] 반환

# Format
[
  {{"field": "필드명", "question": "질문"}},
  {{"field": "필드명2", "question": "질문2"}}
]

# Context
## 사용자 프로필
{profile}

## 질문 목록
{questions_json}

# Query
위 프로필에 **명시적으로** 답이 적힌 질문만 제외하고, 나머지는 그대로 JSON 배열로 반환하세요. 헷갈리면 질문을 유지하세요. 코드 블록 없이 JSON 배열만 출력하세요."""


def build_profile_extract_prompt(
    user_message: str,
    question_text: str = "",
    field_name: str = "",
) -> str:
    """사용자 답변에서 프로필 정보를 추출하는 프롬프트 생성.
    
    Args:
        user_message: 사용자가 입력한 답변
        question_text: 물었던 질문 전문
        field_name: 질문이 매핑되는 필드명 (선택)
    
    Returns:
        Solar에 전달할 프롬프트 문자열
    """
    field_hint = f"\n필드명 힌트: {field_name}" if field_name else ""
    
    return f"""# Role
당신은 사용자 답변에서 프로필 정보를 추출하는 전문가입니다.

# Instructions
질문과 사용자 답변을 분석하여 프로필에 추가할 필드명과 값을 JSON으로 반환하세요.

## 추출 원칙
- 답변에서 명확히 확인된 정보만 추출
- 필드명은 한국어로 간결하게 (예: "주식거래여부", "자녀수", "자동차보유")
- 값은 구체적이고 명확하게 (예: "있음", "없음", "2명")

# Constraints
- Return ONLY valid JSON object
- NEVER add explanations or markdown
- 키: 필드명 (한국어)
- 값: 문자열
- 답변에서 추출할 정보가 없으면 빈 객체 {{}} 반환

# Format
{{
  "필드명1": "값1",
  "필드명2": "값2"
}}

# Context
질문: {question_text}{field_hint}

사용자 답변: {user_message}

# Query
위 답변에서 프로필 필드를 추출하여 JSON으로 반환하세요. 코드 블록 없이 JSON만 출력하세요."""


def build_solar_prompt(
    profile: str,
    policy_text: str,
    agent_plan: str,
    answered_fields: Optional[str],
    ie_extract: Optional[str],
) -> str:
    """최종 상담 결과 생성 프롬프트.
    
    Args:
        profile: 구조화된 프로필 문자열
        policy_text: 정책 본문
        agent_plan: Plan 단계 결과 JSON 문자열
        answered_fields: 사용자가 답한 필드 JSON 문자열 (선택)
        ie_extract: Information Extraction 결과 (선택)
    
    Returns:
        Solar에 전달할 프롬프트 문자열
    """
    answered_section = ""
    if answered_fields:
        answered_section = f"""
## 추가 확인된 정보
{answered_fields}
"""
    
    ie_section = ""
    if ie_extract:
        ie_section = f"""
## 추출된 핵심 정보 (참고용)
{ie_extract}
"""
    
    return f"""# Role
당신은 정부 정책을 개인 맞춤형 행동 가이드로 변환하는 정책 상담 전문가입니다.

# Instructions
사용자 프로필, 정책 문서, Agent 분석 결과를 종합하여 최종 상담 결과를 생성하세요.

## 출력 구조 (MANDATORY)
반드시 아래 5개 섹션을 정확한 헤더명으로 포함해야 합니다:

**[자격 판단]**
- 각 정책별 자격 충족 여부와 구체적 이유
- "자격 충족", "자격 미충족", "자격 판단 필요" 중 하나로 명시

**[신청 가능 정책]**
- 지금 당장 신청할 수 있는 정책 2~3가지
- 각 정책의 간단한 설명 포함

**[예상 혜택]**
- 각 정책의 구체적이고 실질적인 혜택
- 금액, 비율, 기간 등 정량적 정보 포함

**[다음 단계]**
- 구체적이고 실행 가능한 행동 순서
- 번호 매기기로 명확하게 제시

**[확인 필요 사항]**
- 더 정확한 판단을 위해 추가로 확인이 필요한 정보
- 구체적인 확인 항목 나열

# Constraints
- CRITICAL: 위 5개 헤더를 정확히 사용 (대괄호 [...] 포함)
- 정책 본문과 Agent 분석에 근거한 내용만 작성
- 구체적이고 실행 가능한 안내 제공
- NEVER use markdown bold (**text**) - 터미널 출력용
- 근거 없는 추측이나 할루시네이션 금지

# VERIFICATION CHECKLIST
응답 전 반드시 확인:
1. [자격 판단] 섹션이 있는가?
2. [신청 가능 정책] 섹션이 있는가?
3. [예상 혜택] 섹션이 있는가?
4. [다음 단계] 섹션이 있는가?
5. [확인 필요 사항] 섹션이 있는가?
6. 각 섹션에 구체적인 내용이 포함되어 있는가?
7. 정책 본문에 근거한 내용인가?

# Context
## 사용자 프로필
{profile}
{answered_section}

## Agent 분석 결과
{agent_plan}

## 정책 문서
{policy_text}
{ie_section}

# Query
위 정보를 종합하여 최종 상담 결과를 생성하세요. 5개 필수 섹션을 모두 포함하고, 구체적이고 실행 가능한 안내를 제공하세요."""
