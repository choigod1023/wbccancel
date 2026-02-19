FROM python:3.12-slim

# 파이썬 기본 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY wbc_monitor.py .

# 기본 체크 주기 (초) - 필요하면 컨테이너 실행 시 덮어쓸 수 있음
ENV WBC_INTERVAL=60

# 실행
CMD ["python", "wbc_monitor.py"]

