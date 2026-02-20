# WBC 2026 티켓 매수 건수 모니터

[東京プール主催者公認リセールサービス](https://tradead.tixplus.jp/wbc2026) 페이지에서 **매수가(件)** 가 바뀌면 Discord로 알림을 보냅니다.

## 준비

1. **Python 3.10+** 설치
2. **Discord 웹훅 URL** 발급  
   - 알림 받을 서버 → 채널 설정 → 연동 → 웹후크 → 새 웹후크 만들기 → URL 복사

## 설치

```bash
cd c:\Users\user\Documents\wbc
pip install -r requirements.txt
```

## 사용

### 환경 변수로 웹훅 설정 (권장)

**Windows (PowerShell, 한 번만):**
```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/여기에_본인_웹훅_URL"
python wbc_monitor.py
```

**Windows (영구):**  
시스템 환경 변수에 `DISCORD_WEBHOOK_URL` 추가하거나, 배치 파일에서 설정 후 실행.

**선택 환경 변수**
- `DISCORD_WEBHOOK_URL` — (필수) Discord 웹훅 URL
- `WBC_INTERVAL` — 체크 간격(초). 기본값 `60`. **최소 30초** (너무 짧으면 서버가 봇으로 인식해 빈 페이지를 주거나 차단할 수 있음)

### 한 번만 실행 (테스트)

```powershell
$env:DISCORD_WEBHOOK_URL = "본인_웹훅_URL"
python -c "from wbc_monitor import run_once; run_once()"
```

### 계속 모니터링 (백그라운드)

```powershell
$env:DISCORD_WEBHOOK_URL = "본인_웹훅_URL"
python wbc_monitor.py
```

- `WBC_INTERVAL` 초마다 페이지를 조회하고, 이전 결과와 비교해 **건수 변경**이 있으면 Discord로 알림을 보냅니다.
- 이전 상태는 `wbc_state.json`에 저장됩니다.

## 동작 요약

- 페이지에서 날짜·시간별 **N件** 매수 건수를 파싱합니다.
- 직전 조회 결과와 비교해 **증가/감소**가 있으면 Discord 임베드로 알림을 보냅니다.
- “현재 매수 가능” 요약도 함께 표시됩니다.

## Docker로 실행

### 이미지 빌드

- **Windows (PowerShell / CMD)**  

```bash
cd c:\Users\user\Documents\wbc
docker build -t wbc-monitor .
```

- **Linux / macOS / WSL**

```bash
cd /path/to/wbc   # 예: /home/ubuntu/wbc
docker build -t wbc-monitor .
```

### 컨테이너 실행

- **Windows (PowerShell)^**

```powershell
docker run -d `
  --name wbc-monitor `
  -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/여기에_본인_웹훅_URL" `
  -e WBC_INTERVAL=60 `
  wbc-monitor
```

- **Linux / macOS / WSL**

```bash
docker run -d \
  --name wbc-monitor \
  -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/여기에_본인_웹훅_URL" \
  -e WBC_INTERVAL=60 \
  wbc-monitor
```

- `DISCORD_WEBHOOK_URL`는 **필수**입니다.
- `WBC_INTERVAL`은 선택(초 단위, 기본 60초).
- `wbc_state.json`은 컨테이너 안 `/app` 디렉터리에 저장됩니다.  
  필요하다면 호스트에 저장하려고 할 때:

- **Windows (PowerShell)**

```powershell
docker run -d `
  --name wbc-monitor `
  -e DISCORD_WEBHOOK_URL="웹훅_URL" `
  -e WBC_INTERVAL=60 `
  -v C:\Users\user\Documents\wbc-data:/app `
  wbc-monitor
```

- **Linux / macOS / WSL**

```bash
docker run -d \
  --name wbc-monitor \
  -e DISCORD_WEBHOOK_URL="웹훅_URL" \
  -e WBC_INTERVAL=60 \
  -v /home/ubuntu/wbc-data:/app \
  wbc-monitor
```

## 주의

- 웹훅 URL은 외부에 노출되지 않도록 관리하세요.
- 사이트 구조가 바뀌면 파싱이 실패할 수 있습니다. 그때는 스크립트 수정이 필요할 수 있습니다.
- **24/7 요청 시**: 체크 간격을 너무 짧게(예: 10초) 하면 서버가 봇으로 판단해 빈 페이지를 주거나 접속을 제한할 수 있습니다. 최소 30초 이상 간격을 권장합니다. 요청 헤더는 브라우저와 비슷하게 맞춰 두었습니다.
