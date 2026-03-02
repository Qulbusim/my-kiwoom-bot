# my-kiwoom-bot

키움 OpenAPI+ 기반 트레이딩 봇<br>
테스트용 샘플 전략(관심종목 중 등락률 상위 매수)

#### Conda 32비트 가상환경 설정
1. `set CONDA_FORCE_32BIT=1`
2. `conda create -n <환경명> python=<버전>`
3. `conda config --env --set subdir win-32`

#### settings
- account_index: 거래할 계좌 선택
- request_limit: 요청 제한
- paths: 이벤트 로그 저장 경로
- fee: 수수료
- WEBHOOK_URL: 디스코드 웹훅 URL(미입력시 비활성화)

#### strategy
- stock_list: 관심종목 리스트
- risk: 계좌 위험 관리