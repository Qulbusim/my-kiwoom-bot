import uuid

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import pandas as pd


class Semiconductor(QObject):
    order_signal = pyqtSignal(dict)
    tr_signal = pyqtSignal(dict)
    realtime_signal = pyqtSignal(dict)
    alert_signal = pyqtSignal(str)

    def __init__(self, settings_cfg, strategy_cfg):
        super().__init__()
        # config
        self.settings_cfg = settings_cfg
        self.strategy_cfg = strategy_cfg

        # 수수료
        self.sell_fee_rate = None # 매도 수수료
        self.buy_fee_rate = None # 매수 수수료

        # risk
        self.max_positions = None # 최대 보유종목 수
        self.max_order_amount_krw = None # 주문금액 상한
        self.max_daily_loss_krw = None # 일 최대 손실
        self.take_profit_pct = None
        self.stop_loss_pct = None

        # 손익
        self.daily_realized_pnl = 0 # 당일실현손익, 계좌 변동시 갱신
        self.daily_total_pnl = 0 # 당일 총손익

        # 타이머
        self.cal_strategy_timer = QTimer()
        self.cal_strategy_timer.timeout.connect(self.cal_strategy)
        self.stop_loss_timer = QTimer()
        self.stop_loss_timer.timeout.connect(self.balance_stop_loss)
        self.sl_tp_timer = QTimer()
        self.sl_tp_timer.timeout.connect(self.sl_tp)

        # data
        self.holdings = pd.DataFrame(columns=["종목명","현재가","매입단가","보유수량","가능수량","평가손익"])
        self.watchlist = pd.DataFrame(columns=["종목명","현재가","등락률"]).astype({"등락률": "float64"})

        # 기타
        self.stop_order = False
        self._init_done = set()
        self.ordered_codes = set()

    def strategy_start(self):
        self.load_strategy_cfg()
        self.load_settings_cfg()
        self.request_init_tr()

    def _start_runtime(self):
        if len(self._init_done) == 3: # daily_realized_pnl, holdings, watchlist
            self.stop_loss_timer.start(1000) # ms
            self.cal_strategy_timer.start(1000) # ms
            self.sl_tp_timer.start(200) # ms

    # ---------------------------------------------------------------------
    # emit
    # ---------------------------------------------------------------------
    def emit_order_request(self, payload: dict): # { "method":"send_order", "kwargs":{} }
        self.order_signal.emit(payload)

    def emit_tr_request(self, payload: dict): # { "method":"comm_rq_data", "kwargs":{} }
        self.tr_signal.emit(payload)

    def emit_realtime_request(self, payload: dict): # {"code_list": "", "fid_list": ""}
        self.realtime_signal.emit(payload)

    def emit_alert(self, msg: str):
        self.alert_signal.emit(msg)

    # ---------------------------------------------------------------------
    # 요청 빌더
    # ---------------------------------------------------------------------
    def strategy_req_order(self, order_type: int, code: str, qty: int, price: int, hoga_gb: str, org_order_no: str):
        if self.can_buy(order_type):
            payload = {
                "method": "send_order",
                "kwargs": {
                    "order_type": order_type,
                    "code": code,
                    "qty": qty,
                    "price": price,
                    "hoga_gb": hoga_gb,
                    "org_order_no": org_order_no,
                }
            }
            self.emit_order_request(payload)

    def strategy_req_tr(self, method: str, setinput: dict, kwargs: dict):
        payload = {
            "method": method, # send_condition, comm_rq_data, comm_condition_load
            "setinput": setinput, # comm_rq_data의 경우 setinputvalue 값을 채워 넣어야 됨
            "kwargs": kwargs,
        }
        self.emit_tr_request(payload)

    def strategy_req_realtime(self, code_list, fid_list):
        payload = {
            "code_list": code_list,
            "fid_list": fid_list,
        }
        self.emit_realtime_request(payload)

    # ---------------------------------------------------------------------
    # Config Loader
    # ---------------------------------------------------------------------
    def load_strategy_cfg(self):
        # 관심종목 실시간 시세 신청
        stock_list = self.strategy_cfg.get("stock_list")
        for name, code in stock_list.items():
            self.watchlist.loc[code, "종목명"] = name
            self.watchlist.loc[code, "현재가"] = 0
            self.watchlist.loc[code, "등락률"] = 0

        code_list = ";".join(self.watchlist.index.astype(str).tolist())
        fid_list = "10;12;20" # 현재가;등락률;체결시간
        self.strategy_req_realtime(code_list, fid_list)

        # risk 불러오기
        self.max_positions = int(self.strategy_cfg.get("risk").get("max_positions"))
        self.max_order_amount_krw = int(self.strategy_cfg.get("risk").get("max_order_amount_krw"))
        self.max_daily_loss_krw = int(self.strategy_cfg.get("risk").get("max_daily_loss_krw"))
        self.take_profit_pct = float(self.strategy_cfg.get("risk").get("take_profit_pct"))
        self.stop_loss_pct = float(self.strategy_cfg.get("risk").get("stop_loss_pct"))

    def load_settings_cfg(self):
        # 수수료 불러오기
        broker_fee_rate = float(self.settings_cfg.get("fee").get("broker_fee_rate"))
        exchange_fee_rate = float(self.settings_cfg.get("fee").get("exchange_fee_rate"))
        tax_rate = float(self.settings_cfg.get("fee").get("tax_rate"))

        self.sell_fee_rate = broker_fee_rate + exchange_fee_rate + tax_rate
        self.buy_fee_rate = broker_fee_rate + exchange_fee_rate

    # ---------------------------------------------------------------------
    # 이벤트 수신
    # ---------------------------------------------------------------------
    def save_market_event(self, payload: dict):
        code = payload.get("종목코드")
        현재가 = payload.get("현재가")
        등락률 = payload.get("등락률")
        체결시간 = payload.get("체결시간")

        if code in self.watchlist.index: # 관심종목 시세 갱신
            self.watchlist.loc[code, "현재가"] = 현재가
            self.watchlist.loc[code, "등락률"] = 등락률

        if code in self.holdings.index: # 보유종목 현재가 변동시 데이터프레임 갱신
            self.holdings.loc[code, "현재가"] = 현재가
            self.holdings.loc[code, "평가손익"] = self.calculate_realtime_pnl(code)

    def save_chejan_event(self, payload: dict):
        if payload.get("구분") == "0": # 접수, 체결 시
            주문번호 = payload.get("주문번호")
            code = payload.get("종목코드")
            종목명 = payload.get("종목명")
            주문수량 = payload.get("주문수량", 0)
            주문가격 = payload.get("주문가격", 0)
            미체결수량 = payload.get("미체결수량", 0)
            원주문번호 = payload.get("원주문번호")
            주문구분 = payload.get("주문구분")
            매매구분 = payload.get("매매구분")
            주문체결시간 = payload.get("주문체결시간")
            체결가 = payload.get("체결가", 0)
            체결량 = payload.get("체결량", 0)
            현재가 = payload.get("현재가", 0)
            단위체결가 = payload.get("단위체결가", 0)
            단위체결량 = payload.get("단위체결량", 0)
            당일매매수수료 = payload.get("당일매매수수료", 0)
            당일매매세금 = payload.get("당일매매세금", 0)

            if 미체결수량 == 0:
                self.ordered_codes.discard(code)

        elif payload.get("구분") == "1": # 국내주식 잔고변경 시
            code = payload.get("종목코드")
            종목명 = payload.get("종목명")
            현재가 = payload.get("현재가", 0)
            보유수량 = payload.get("보유수량", 0)
            매입단가 = payload.get("매입단가", 0)
            매도매수구분 = payload.get("매도매수구분")
            주문가능수량 = payload.get("주문가능수량", 0)
            # 주문체결시간 = payload.get("주문체결시간")
            # 손익률 = payload.get("손익률")
            # 당일매매수수료 = payload.get("당일매매수수료", 0)
            # 당일매매세금 = payload.get("당일매매세금", 0)
            self.daily_realized_pnl = payload.get("당일실현손익", 0)

            주당총비용 = 현재가 * self.sell_fee_rate + 매입단가 * self.buy_fee_rate
            평가손익 = (현재가 - 매입단가 - 주당총비용) * 보유수량
            self.holdings.loc[code, "종목명"] = 종목명
            self.holdings.loc[code, "현재가"] = 현재가
            self.holdings.loc[code, "매입단가"] = 매입단가
            self.holdings.loc[code, "보유수량"] = 보유수량
            self.holdings.loc[code, "가능수량"] = 주문가능수량
            self.holdings.loc[code, "평가손익"] = 평가손익

            if 매도매수구분 == '1' and (보유수량 == 0):  # 전량매도시
                self.holdings.drop(code, inplace=True)

    def receive_daily_realized_pnl(self, daily_realized_pnl):
        self.daily_realized_pnl = daily_realized_pnl
        self._init_done.add("daily_realized_pnl")
        self._start_runtime()

    def receive_balance_info(self, payload: dict):
        for code, item in payload.items():
            self.holdings.loc[code, "종목명"] = item.get("종목명")
            self.holdings.loc[code, "현재가"] = item.get("현재가", 0)
            self.holdings.loc[code, "매입단가"] = item.get("매입단가", 0)
            self.holdings.loc[code, "보유수량"] = item.get("보유수량", 0)
            self.holdings.loc[code, "평가손익"] = item.get("평가손익", 0)
        self._init_done.add("holdings")
        self._start_runtime()

    def receive_watch_list_info(self, payload: dict):
        for code, item in payload.items():
            self.watchlist.loc[code, "종목명"] = item.get("종목명")
            self.watchlist.loc[code, "현재가"] = item.get("현재가", 0)
            self.watchlist.loc[code, "등락률"] = item.get("등락률", 0)
        self._init_done.add("watchlist")
        self._start_runtime()

    # ---------------------------------------------------------------------
    # 전략 계산
    # ---------------------------------------------------------------------
    def cal_strategy(self):
        """
        테스트용 샘플 전략
        관심종목 중 등락률이 제일 높은 종목 매수
        다른 종목이 2% 초과 등락률이 높아질 경우 갈아탐
        """
        watchlist = self.watchlist[self.watchlist["등락률"] < 27] # 상한가 따라잡기 제외(미체결 가능성)
        highest_code =  watchlist["등락률"].idxmax() # 관심종목중 최고 등락률(code)
        highest_rate = watchlist.loc[highest_code, "등락률"]
        hold_codes = self.holdings.index.intersection(watchlist.index) # holdings중 watchlist에 있는 코드들
        if len(hold_codes) == 0:
            holdings_high_code = ""
            holdings_high_rate = -33
        else:
            holdings_high_code = watchlist.loc[hold_codes, "등락률"].idxmax()
            holdings_high_rate = watchlist.loc[holdings_high_code, "등락률"]
        if holdings_high_rate + 2 < highest_rate:
            # sell holdings_high
            if holdings_high_code in self.holdings.index and holdings_high_code not in self.ordered_codes:
                order_type = 2  # 신규매도
                code = holdings_high_code
                qty = self.holdings.loc[code, "보유수량"]
                price = 0
                hoga_gb = "03"
                org_order_no = ""
                self.strategy_req_order(order_type, code, qty, price, hoga_gb, org_order_no)
                self.ordered_codes.add(code)

            # buy highest
            # can_buy()로 인해 save_chejan_event()에서 매도 확인 후 주문 방식이 맞으나, 테스트용으로 cal_strategy()에 위치
            if highest_code not in self.ordered_codes:
                order_type = 1  # 신규매수
                code = highest_code
                qty = self.calculate_qty(self.watchlist.loc[code, "현재가"])
                price = 0
                hoga_gb = "03"
                org_order_no = ""
                self.strategy_req_order(order_type, code, qty, price, hoga_gb, org_order_no)
                self.ordered_codes.add(code)

    # ---------------------------------------------------------------------
    # 기타
    # ---------------------------------------------------------------------
    def request_init_tr(self):
        # daily_realized_pnl 초기화
        method = "comm_rq_data"
        setinput = {
            "계좌번호": None,
            "비밀번호": "",
            "종목코드": None,
        }
        kwargs = {
            "rq_name": "comm_rq_data",
            "tr_code": "opt10077",
            "prev_next": 0,
            "screen_no": None,

        }
        self.strategy_req_tr(method=method, setinput=setinput, kwargs=kwargs)

        # holdings 초기화
        method = "comm_rq_data"
        setinput = {
            "계좌번호": None,
            "비밀번호": "",
            "비밀번호입력매체구분": "00",
            "조회구분": 2,
            "거래소구분": "",
        }
        kwargs = {
            "rq_name": "comm_rq_data",
            "tr_code": "opw00018",
            "prev_next": 0,
            "screen_no": None,
        }
        self.strategy_req_tr(method=method, setinput=setinput, kwargs=kwargs)

        # watchlist 초기화
        method = "comm_kw_rq_data"
        setinput = {}
        kwargs = {
            "arr_code": ";".join(self.watchlist.index.astype(str).tolist()),
            "next_": 0,
            "code_count": len(self.watchlist.index),
            "type_flag": 0,
            "rq_name": "comm_kw_rq_data",
            "screen_no": None,
        }
        self.strategy_req_tr(method=method, setinput=setinput, kwargs=kwargs)

    def balance_stop_loss(self):
        self.daily_total_pnl = self.daily_realized_pnl + self.holdings["평가손익"].sum()
        if self.daily_total_pnl < - self.max_daily_loss_krw: # 최대손실을 넘기면
            self.emit_alert("계좌 스탑로스")
            self.stop_loss_timer.stop()
            for code in self.holdings.index: # 미체결수량이 없을 시(주문을 시장가로 하지 않을 시 수정 필요)
                order_type = 2
                qty = self.holdings.loc[code, "보유수량"]
                price = 0
                hoga_gb = "03"
                org_order_no = ""
                self.strategy_req_order(
                    order_type=order_type,
                    code=code,
                    qty=qty,
                    price=price,
                    hoga_gb=hoga_gb,
                    org_order_no=org_order_no,
                )
            self.stop_order = True

    def sl_tp(self):
        for code in self.holdings.index:
            평가손익 = self.holdings.loc[code, "평가손익"]
            매입단가 = self.holdings.loc[code, "매입단가"]
            보유수량 = self.holdings.loc[code, "보유수량"]
            가능수량 = self.holdings.loc[code, "가능수량"]

            if not 가능수량:
                continue

            if 매입단가 and 보유수량:
                수익률 = 평가손익 / (매입단가 * 보유수량) * 100
            else:
                수익률 = 0

            if 수익률 > self.take_profit_pct and code not in self.ordered_codes: # 익절
                order_type = 2  # 신규매도
                qty = 보유수량
                price = 0
                hoga_gb = "03"
                org_order_no = ""
                self.strategy_req_order(order_type, code, qty, price, hoga_gb, org_order_no)
                self.ordered_codes.add(code)

            elif 수익률 < self.stop_loss_pct and code not in self.ordered_codes: # 손절
                order_type = 2  # 신규매도
                qty = 보유수량
                price = 0
                hoga_gb = "03"
                org_order_no = ""
                self.strategy_req_order(order_type, code, qty, price, hoga_gb, org_order_no)
                self.ordered_codes.add(code)

    def calculate_qty(self, 현재가: int) -> int:
        return self.max_order_amount_krw // 현재가

    def calculate_realtime_pnl(self, code: str) -> int:
        현재가 = self.holdings.loc[code, "현재가"]
        매입단가 = self.holdings.loc[code, "매입단가"]
        보유수량 = self.holdings.loc[code, "보유수량"]

        주당총비용 = 현재가 * self.sell_fee_rate + 매입단가 * self.buy_fee_rate
        평가손익 = (현재가 - 매입단가 - 주당총비용) * 보유수량
        return 평가손익

    def can_buy(self, order_type: int) -> bool:
        if self.stop_order: # 계좌 스탑로스
            self.emit_alert("계좌 스탑로스")
            return False
        if len(self.holdings) >= self.max_positions and order_type in (1, 11): # 최대 보유수 이상시 매수금지
            self.emit_alert("max_positions 도달")
            return False
        return True
