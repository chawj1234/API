# 데모 실행 가이드

> 이 문서는 **처음 사용하는 분**도 그대로 따라 실행할 수 있도록 단계별로 정리되었습니다.

---

## 📦 시작 전 준비물

> 실행 전에 아래 항목이 준비되어 있는지 확인하세요.

| 항목 | 설명 | 확인 명령어 |
|------|------|-----------|
| **Python 3.9+** | 프로그램 실행 환경 | `python --version` |
| **pip** | 패키지 설치 도구 | `pip --version` |
| **git** | 코드 다운로드 | `git --version` |
| **Upstage API 키** | AI 서비스 인증 | 아래 안내 참고 |

### 🔑 Upstage API 키 발급

1. [Upstage Console](https://console.upstage.ai) 접속
2. 회원가입 또는 로그인
3. **API Keys** 메뉴에서 새 키 생성
4. `up_xxxxxxxx...` 형태의 키 복사
> ⚠️ API 키는 외부에 노출되지 않도록 주의하세요.

---

## 🚀 설치 및 실행

### Step 1. 코드 다운로드
```bash
git clone https://github.com/chawj1234/Policy-Agent.git
cd Policy-Agent/policy-navigator-agent
```

### Step 2. 가상환경 생성 및 활성화

> 💡 **가상환경**은 프로젝트별로 독립된 Python 환경을 만들어  
> 라이브러리 충돌을 방지하기 위한 표준적인 방법입니다.

```bash
# 가상환경 생성 (최초 1회)
python -m venv .venv

# 가상환경 활성화
# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

활성화되면 터미널에 `(.venv)`가 표시됩니다.

### Step 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### Step 4. 환경변수 설정

`.env` 파일을 생성하고 Upstage API 키를 입력합니다:

```bash
방법 1) 터미널에서 생성
# .env 파일 생성
cat > .env << EOF
UPSTAGE_API_KEY=up_여기에_발급받은_키_입력
UPSTAGE_BASE_URL=https://api.upstage.ai
SOLAR_MODEL=solar-pro3
EOF
```

```bash
방법 2) 직접 파일 생성
# 프로젝트 루트 디렉토리에 .env 파일을 만들고, 아래 내용을 그대로 입력하세요.
UPSTAGE_API_KEY=up_여기에_발급받은_키_입력
UPSTAGE_BASE_URL=https://api.upstage.ai
SOLAR_MODEL=solar-pro3
```

### Step 5. 데모 실행
```bash
# 기본: 금융·재정·조세 정책 (data/finance_policy.pdf)
python src/main.py --profile "29세/수도권/중소기업/월250/미혼"

# 다른 정책(국토·교통)으로 데모
python src/main.py --profile "29세/수도권/중소기업/월250/미혼" --pdf data/transportation_policy.pdf
```
> `--pdf` 옵션을 생략하면 기본 정책(`finance_policy.pdf`)이 사용됩니다.

---

## 📋 프로필 입력 형식

프로필은 **슬래시(`/`)로 구분된 단일 문자열**로 입력합니다.

```
"나이/지역/직업(또는 상태)/월소득/혼인상태"
```

| 항목 | 예시 | 설명 |
|------|------|------|
| 나이 | `29세` | 만 나이 |
| 지역 | `수도권`, `지방`, `서울` | 거주 지역 |
| 직업 | `중소기업`, `대학생`, `구직중` | 현재 상태 |
| 월소득 | `월250`, `월0`, `월400` | 만원 단위 |
| 혼인 | `미혼`, `기혼`, `기혼/자녀1` | 가족 상황 |

### 프로필 예시
```bash
# 청년 직장인 (기본: 금융·재정·조세)
python src/main.py --profile "29세/수도권/중소기업/월250/미혼"

# 대학생
python src/main.py --profile "22세/지방/대학생/월50/미혼"

# 취업준비생
python src/main.py --profile "28세/수도권/구직중/월0/미혼"

# 신혼부부 + 국토·교통 정책
python src/main.py --profile "32세/수도권/대기업/월400/기혼/자녀1" --pdf data/transportation_policy.pdf
```

---

## 🔄 실행 흐름 (사용자 관점)

**한 번의 피드백 루프**(질문 → 답변 → 재분석 → 최종)로 동작합니다. 에이전트가 부족한 정보를 질문하고, 답변을 반영해 재분석한 뒤 최종 안내를 출력합니다.

```
프로필 입력
   ↓
정책 PDF 파싱 (Document Parse)
   ↓
핵심 정보 구조화 (Information Extraction, 보조)
   ↓
조건 판단 & 질문 생성 (Solar)
   ↓
사용자 답변 반영
   ↓
최종 행동 가이드 출력
```

### 용어 설명

| 용어 | 역할 |
|------|------|
| **Document Parse** | PDF 문서를 AI가 읽을 수 있는 텍스트로 변환 |
| **Information Extraction** | 정책명, 대상, 혜택 등 핵심 정보를 구조화 (보조 역할) |
| **Solar** | Upstage의 AI 모델. 조건 분석, 질문 생성, 행동 가이드 설계 담당 |

---

## 💬 대화형 입력 예시

실행하면 이런 화면이 나옵니다:

```
📄 PDF 파싱 중: data/finance_policy.pdf
✅ PDF 파싱 완료

🔍 정책 분석 중...
✅ 분석 완료

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 추가 정보가 필요합니다:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ 현재 월 소득이 중위소득 150% 이하에 해당하나요?
👉 네, 250만원입니다

❓ 현재 재직 중이신가요, 아니면 구직 활동 중이신가요?
👉 재직 중입니다

❓ 기존에 다른 청년 지원 사업을 받고 계신가요?
👉 아니요

🔄 정보를 반영하여 재분석 중...
✅ 재분석 완료

📝 최종 상담 결과 생성 중...
✅ 완료
```

---

## 📊 결과 해석 가이드

출력 결과는 **5개 섹션**으로 구성됩니다:

| 섹션 | 설명 |
|------|------|
| **[자격 판단]** | 각 정책의 자격 요건 충족 여부와 이유 |
| **[신청 가능 정책]** | 내가 신청할 수 있는 정책 2~3가지 |
| **[예상 혜택]** | 각 정책 신청 시 받을 수 있는 구체적 혜택 |
| **[다음 단계]** | 지금 당장 해야 할 행동 순서 |
| **[확인 필요 사항]** | 더 정확한 판단을 위해 확인할 정보 |

---

## ⚠️ 문제 해결

### API 키 오류
```
ValueError: UPSTAGE_API_KEY 환경변수가 필요합니다.
```
→ `.env` 파일에 API 키가 올바르게 입력되었는지 확인

### PDF 파일 없음
```
FileNotFoundError: data/finance_policy.pdf
```
→ `data/` 폴더에 `finance_policy.pdf`(기본) 또는 사용 중인 `--pdf` 경로의 파일이 있는지 확인

### 가상환경 미활성화
```
ModuleNotFoundError: No module named 'typer'
```
→ `source .venv/bin/activate` 실행 후 다시 시도

### 토큰 초과 오류
```
BadRequestError: maximum context length
```
→ PDF 파일이 너무 큰 경우 발생. 더 작은 PDF 사용 권장

---

## 🔍 도움말

```bash
python src/main.py --help
```

```
Usage: main.py [OPTIONS]

  정책 상담 AI Agent - 항상 대화형으로 동작합니다.

Options:
  --profile TEXT  사용자 프로필 문자열  [required]
  --pdf TEXT      정책 PDF 경로 (기본: data/finance_policy.pdf. 예: data/transportation_policy.pdf)
  --help          Show this message and exit.
```

---
