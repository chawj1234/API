# Policy Navigator Agent

## 프로젝트 개요

정부 정책 문서를 개인 맞춤형 행동 가이드로 변환하는 AI Agent 프로토타입입니다.

**핵심 기술:**
- **Upstage Solar**: 정책 분석, 조건 판단, 행동 가이드 생성
- **Upstage Document Parse**: PDF 문서 파싱 및 구조화
- **Upstage Information Extraction**: 핵심 슬롯 추출(보조 신호)

## 왜 Agent인가

정책 문서는 조건과 예외가 많고, 사용자는 자신의 상황에 맞는 "다음 행동"이 필요합니다.

Agent는 **판단(조건 검증) → 계획(선택지 구성) → 대화(피드백 루프) → 실행(행동 가이드)** 흐름을 통해 실제 신청 가능성 중심의 맞춤형 가이드를 제공합니다.

## Agent 흐름 다이어그램

```
[사용자 프로필 입력]
          ↓
[Document Parse API] ─── PDF 파싱
          ↓
[Information Extraction] ─── 핵심 정보 추출 (보조 신호)
          ↓
[Solar Plan 단계] ─── 조건 분석, 질문 생성
          ↓
[대화형 입력] ─── 부족한 정보 질문/응답
          ↓
[Solar Final 단계] ─── 최종 행동 가이드 생성
          ↓
[자격 판단 / 신청 가능 정책 / 예상 혜택 / 다음 단계 / 확인 필요 사항]
```

## Upstage 제품 역할

| 제품 | 역할 |
|------|------|
| **Solar** | 오케스트레이터(판단/계획/검증), 최종 행동 가이드 생성 |
| **Document Parse** | PDF 문서 파싱(텍스트/구조 추출) |
| **Information Extract** | 정책 문서의 의미 슬롯 추출(보조 신호) |

**역할 분리 설명:**
> 정책 문서는 형식이 제각각인 반정형 문서입니다.  
> Document Parse는 텍스트/구조를 확보하고,  
> Information Extract는 `program_name`, `benefit`, `required_documents` 등 핵심 슬롯을 보조적으로 추출합니다.  
> 추출 결과가 없거나 불완전해도 정책 원문을 1차 근거로 사용합니다.  
> 최종 판단·질문 생성·행동 설계는 Solar가 담당하여 문맥 기반 의사결정을 유지합니다.

## 빠른 시작

### 1. 환경 설정

```bash
cd policy-navigator-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. .env 파일 생성

```bash
cp .env.example .env
# .env 파일을 열고 API 키 설정
```

**.env 예시:**
```
UPSTAGE_API_KEY=up_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
UPSTAGE_BASE_URL=https://api.upstage.ai
SOLAR_MODEL=solar-pro2
```

### 3. 실행

```bash
python src/main.py --profile "29세/수도권/중소기업/월250/미혼"
```

> 기본적으로 `data/sample_policy.pdf`를 Document Parse API로 파싱하여 사용합니다.

## 데모 정책 문서

| 항목 | 내용 |
|------|------|
| **파일** | `data/sample_policy.pdf` |
| **출처** | 기획재정부 「2026년부터 이렇게 달라집니다」 (2025.12.29 배포) |
| **발췌 범위** | 02장 교육·보육·가족 (p.60~) ~ 03장 보건·복지·고용 (~p.129) |
| **페이지** | 약 70페이지 |
| **포함 정책** | ICL 학자금대출 확대, 국민연금 크레딧 확대, 위기아동청년법, 먹거리 기본보장 등 |

> 실제 정부 정책 문서에서 청년·복지 관련 카테고리를 발췌하여 데모용으로 구성했습니다.

## 데모 시나리오

- **입력 프로필**: "29세/수도권/중소기업/월250/미혼"
- **정책 문서**: 위 발췌 문서 (`data/sample_policy.pdf`)
- **출력**: 청년미래적금, K-패스 환급, 중소기업 한끼 지원 등 맞춤형 가이드

## 출력 예시

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 최종 상담 결과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[자격 판단]
- 청년미래적금: 만 19~34세 청년 대상으로 해당 가능성 높음
- K-패스 청년 환급: 30% 환급율 적용 대상
- 중소기업 든든한 한끼: 중소기업 재직자로 대상에 해당

[신청 가능 정책]
1) 청년미래적금 가입 (자산형성)
2) K-패스 청년 등록 (교통비 절감)
3) 든든한 한끼 신청 (식비 지원)

[예상 혜택]
- 청년미래적금: 정부 매칭으로 자산형성 가속화
- K-패스: 월 교통비 30% 환급 (연간 약 20만원 절감)
- 든든한 한끼: 월 4만원 한도 점심값 지원

[다음 단계]
1. K-패스 앱에서 청년 등록 신청
2. 청년미래적금 출시 시 시중은행 앱에서 가입
3. 회사 인사팀에 든든한 한끼 사업 참여 여부 문의

[확인 필요 사항]
- 현재 K-패스를 사용 중이신가요?
```

## 프로젝트 구조

```
policy-navigator-agent/
├── src/
│   ├── main.py           # CLI 진입점 (항상 대화형)
│   ├── agent.py          # Agent 핵심 로직 (Plan → 대화 → Final)
│   ├── prompts.py        # Solar 프롬프트 템플릿
│   ├── upstage_client.py # Upstage API 클라이언트 (Solar, Parse, IE)
│   └── config.py         # 환경 설정
├── data/
│   └── sample_policy.pdf # 정책 문서 (Document Parse로 파싱)
├── requirements.txt
├── .env.example
├── DEMO.md
└── README.md
```

## 자세한 데모 가이드

[DEMO.md](DEMO.md) 참조
