# my-kiwoom-bot

키움 OpenAPI+ 기반 트레이딩 봇<br>
테스트용 샘플 전략(관심종목 중 등락률 상위 매수. 실행 시 즉시 시작)

#### 요구사항
1. 32비트 환경
2. 키움증권 계좌
3. Open API+ 사용 신청 및 설치
4. 모의투자 신청(권장)

#### settings
- account_index: 거래할 계좌 선택
- request_limit: 요청 제한
- paths: 이벤트 로그 저장 경로
- fee: 수수료
- WEBHOOK_URL: 디스코드 웹훅 URL(미입력시 비활성화)

#### strategy
- stock_list: 관심종목 리스트
- risk: 계좌 위험 관리