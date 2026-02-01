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

> 프로토타입에서는 **한 번의 피드백 루프**(질문 → 답변 → 재분석 → 최종)로 대화합니다. 에이전트가 부족한 정보를 질문하고, 사용자 답변을 반영해 재분석한 뒤 최종 안내를 냅니다.

## Agent 흐름 다이어그램

```
[사용자 프로필 입력]
          ↓
[Document Parse API] ─── PDF 파싱
          ↓
[Information Extraction] ─── 핵심 정보 추출 (보조 신호)
          ↓
[Solar 1차 분석] ─── 조건 판단, 질문 생성
          ↓
[대화형 입력] ─── 부족한 정보 질문/응답
          ↓
[Solar 2차 분석] ─── 최종 행동 가이드 생성
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

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API 키 입력 후 저장
python src/main.py --profile "29세/수도권/중소기업/월250/미혼"
```

> 설치·설정·프로필 형식·문제 해결 등 상세 가이드는 [DEMO.md](DEMO.md)를 참조하세요.

**모델 선택** (`SOLAR_MODEL` in `.env`): `solar-pro2` (31B, 32K) | [`solar-pro3`](https://www.upstage.ai/blog/ko/solar-pro-3-0127) (102B MoE, 128K, **Free access ~26.03.02**)

## 출력 예시

> ⚠️ 아래는 예시 출력입니다. 실제 결과는 PDF 내용과 Solar 모델 응답에 따라 달라질 수 있습니다.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 최종 상담 결과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[자격 판단]
- ICL 학자금대출: 대학(원)생 대상이므로 현재 해당 없음
- 국민연금 크레딧: 출산/군복무 크레딧은 해당 조건 확인 필요
- 먹거리 기본보장: 취약계층 대상으로 소득 기준 확인 필요

[신청 가능 정책]
1) 기준 중위소득 인상에 따른 복지 혜택 확대 (소득 기준 완화)
2) 위기청년 자립지원 (만 19~24세 해당 시)
3) 청년 주거·취업 지원 정책 (지자체별 확인)

[예상 혜택]
- 기준 중위소득 인상: 복지 수급 기준 완화로 더 많은 지원 가능
- 위기청년 자립지원: 자립수당, 주거지원, 취업연계 서비스
- 청년 지원: 월세 지원, 취업성공패키지 등

[다음 단계]
1. 정부24에서 본인 소득구간 확인
2. 복지로에서 맞춤형 급여 시뮬레이션
3. 거주지 주민센터에서 청년 지원사업 상담

[확인 필요 사항]
- 현재 다른 청년 지원사업을 받고 계신가요?
- 월 소득이 중위소득 150% 이하에 해당하나요?
```

## 프로젝트 구조

```
policy-navigator-agent/
├── src/
│   ├── main.py           # CLI 진입점
│   ├── agent.py          # Agent 핵심 로직 (Plan → 대화 → Final)
│   ├── prompts.py        # Solar 프롬프트 템플릿
│   ├── upstage_client.py # Upstage API 클라이언트 (Solar, Parse, IE)
│   └── config.py         # 환경 설정
├── data/
│   ├── finance_policy.pdf          # 기본: 금융·재정·조세 정책
│   └── transportation_policy.pdf   # 다른 정책: 국토·교통
├── docs/
│   └── Solar Pro 2 Prompting Handbook.pdf  # Solar 프롬프팅 참고
├── DEMO.md               # 상세 데모 가이드
├── requirements.txt
├── .env.example
└── README.md
```

## 자세한 데모 가이드

[DEMO.md](DEMO.md) 참조
