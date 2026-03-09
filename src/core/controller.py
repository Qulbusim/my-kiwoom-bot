from PyQt5.QtCore import QTimer


class Controller:
    def __init__(self, settings, api, strategy, queue, ui, screen_manager, logger, notifier):
        self.settings = settings
        self.api = api
        self.strategy = strategy
        self.queue = queue
        self.ui = ui
        self.screen_manager = screen_manager
        self.logger = logger
        self.notifier = notifier

        self.account_num = None

        # 연결상태를 1초마다 확인 후 ui에 반영
        self.conn_state_timer = QTimer()
        self.conn_state_timer.timeout.connect(self.connection_state_to_ui)
        self.conn_state_timer.start(1000) # ms

    def _controller_start(self):
        self.balance_info()
        self.strategy.strategy_start()

    def wire(self):
        # 1) api -> controller
        self.api.on_event_connect.connect(self._on_api_event_connect)
        self.api.on_receive_tr_data.connect(self._on_api_receive_tr_data)
        self.api.on_receive_chejan_data.connect(self._on_api_receive_chejan_data)
        self.api.on_receive_real_data.connect(self._on_api_receive_real_data)
        self.api.on_receive_condition_ver.connect(self._on_api_receive_condition_ver)
        self.api.on_receive_tr_condition.connect(self._on_api_receive_tr_condition)
        self.api.on_receive_real_condition.connect(self._on_api_receive_real_condition)
        self.api.on_receive_msg.connect(self._on_api_receive_msg)

        # 2) ui -> controller
        self.ui.btn_auto_trade.toggled.connect(self._on_ui_auto_trade_toggled)

        # 3) queue -> controller
        self.queue.to_caller_signal.connect(self._on_queue_request)
        self.queue.left_req_num.connect(self._on_queue_left_count)

        # 4) strategy -> controller
        self.strategy.order_signal.connect(self._on_strategy_order_request)
        self.strategy.tr_signal.connect(self._on_strategy_tr_request)
        self.strategy.realtime_signal.connect(self._on_strategy_realtime_request)
        self.strategy.alert_signal.connect(self._on_strategy_alert)

    # ---------------------------------------------------------------------
    # api -> controller
    # ---------------------------------------------------------------------
    def _on_api_event_connect(self, err_code):
        err_msg_dict = {
            0: "로그인 성공",
            100: "사용자 정보교환 실패",
            101: "서버접속 실패",
            102: "버전처리 실패",
        }
        err_msg = err_msg_dict.get(err_code)
        self.ui.show_app_message(err_msg)
        self.notifier.send_msg(err_msg)
        self.logger.store_event_log(err_msg)

        if err_msg != "로그인 성공":
            return

        self._controller_start()

    def _on_api_receive_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next):
        if tr_code == "opt10077":
            rel = int(self.api.get_comm_data(tr_code, record_name, 0, "당일실현손익").strip())
            self.strategy.receive_daily_realized_pnl(rel)

        elif tr_code == "opw00018":
            balance_info = {}
            data_cnt = self.api.get_repeat_cnt(tr_code=tr_code, rq_name=rq_name)
            for i in range(data_cnt):
                code = self.api.get_comm_data(tr_code, rq_name, i, "종목번호").replace("A", "").strip()
                종목명 = self.api.get_comm_data(tr_code, rq_name, i, "종목명").strip()
                평가손익 = int(self.api.get_comm_data(tr_code, rq_name, i, "평가손익").lstrip("0"))
                매입가 = int(self.api.get_comm_data(tr_code, rq_name, i, "매입가"))
                보유수량 = int(self.api.get_comm_data(tr_code, rq_name, i, "보유수량"))
                현재가 = int(self.api.get_comm_data(tr_code, rq_name, i, "현재가").replace('-', ''))
                매매가능수량 = int(self.api.get_comm_data(tr_code, rq_name, i, "매매가능수량"))
                # 매입수수료 = int(self.api.get_comm_data(tr_code, rq_name, i, "매입수수료"))
                # 평가금액 = int(self.api.get_comm_data(tr_code, rq_name, i, "평가금액"))
                # 평가수수료 = int(self.api.get_comm_data(tr_code, rq_name, i, "평가수수료"))
                # 세금 = int(self.api.get_comm_data(tr_code, rq_name, i, "세금"))
                # 수수료합 = int(self.api.get_comm_data(tr_code, rq_name, i, "수수료합"))

                balance_info[code] = {
                    "종목명": 종목명,
                    "현재가": 현재가,
                    "매입단가": 매입가,
                    "보유수량": 보유수량,
                    "가능수량": 매매가능수량,
                    "평가손익": 평가손익,
                }
            self.strategy.receive_balance_info(balance_info)

        elif tr_code == "OPTKWFID":
            watch_list_info = {}
            data_cnt = self.api.get_repeat_cnt(tr_code=tr_code, rq_name=rq_name)
            for i in range(data_cnt):
                code = self.api.get_comm_data(tr_code, rq_name, i, "종목코드").replace("A", "").strip()
                종목명 = self.api.get_comm_data(tr_code, rq_name, i, "종목명").strip()
                현재가 = int(self.api.get_comm_data(tr_code, rq_name, i, "현재가").replace('-', ''))
                등락률 = float(self.api.get_comm_data(tr_code, rq_name, i, "등락율").strip())

                watch_list_info[code] = {
                    "종목명": 종목명,
                    "현재가": 현재가,
                    "등락률": 등락률,
                }
            self.strategy.receive_watch_list_info(watch_list_info)

    def _on_api_receive_chejan_data(self, gubun: str, item_cnt: int, fid_list: str):
        if gubun == "0": # 접수, 체결 시
            주문번호 = self.api.get_chejan_data(9203).strip()
            code = self.api.get_chejan_data(9001).replace("A", "").strip()
            종목명 = self.api.get_chejan_data(302).strip()
            주문수량 = 0 if len(self.api.get_chejan_data(900)) == 0 else int(self.api.get_chejan_data(900))
            주문가격 = 0 if len(self.api.get_chejan_data(901)) == 0 else int(self.api.get_chejan_data(901))
            미체결수량 = 0 if len(self.api.get_chejan_data(902)) == 0 else int(self.api.get_chejan_data(902))
            원주문번호 = self.api.get_chejan_data(904).strip()
            주문구분 = self.api.get_chejan_data(905).replace("+", "").replace("-", "").strip()
            매매구분 = self.api.get_chejan_data(906).strip()
            주문체결시간 = self.api.get_chejan_data(908).strip()
            체결가 = 0 if len(self.api.get_chejan_data(910)) == 0 else int(self.api.get_chejan_data(910))
            체결량 = 0 if len(self.api.get_chejan_data(911)) == 0 else int(self.api.get_chejan_data(911))
            현재가 = int(self.api.get_chejan_data(10).replace('-', ''))
            단위체결가 = 0 if len(self.api.get_chejan_data(914)) == 0 else int(self.api.get_chejan_data(914))
            단위체결량 = 0 if len(self.api.get_chejan_data(915)) == 0 else int(self.api.get_chejan_data(915))
            당일매매수수료 = 0 if len(self.api.get_chejan_data(938)) == 0 else int(self.api.get_chejan_data(938))
            당일매매세금 = 0 if len(self.api.get_chejan_data(939)) == 0 else int(self.api.get_chejan_data(939))

            # 단위체결량: 방금 체결된 수량, 접수시 0으로 시작함
            if 단위체결량 > 0: # 체결이 됐으면
                msg = (f"체결| 종목명:{종목명}, 현재가:{현재가}, 주문수량:{주문수량}, 주문가격:{주문가격},체결가:{체결가}, "
                       f"주문구분:{주문구분}, 미체결수량:{미체결수량}, 단위체결가:{단위체결가}, 단위체결량:{단위체결량}")
                self.ui.show_app_message(msg)
                self.notifier.send_msg(msg)
                self.logger.store_event_log(msg)

            chejan_event = {
                "구분": gubun,
                "주문번호": 주문번호,
                "종목코드": code,
                "종목명": 종목명,
                "주문수량": 주문수량,
                "주문가격": 주문가격,
                "미체결수량": 미체결수량,
                "원주문번호": 원주문번호,
                "주문구분": 주문구분,
                "매매구분": 매매구분,
                "주문체결시간": 주문체결시간,
                "체결가": 체결가,
                "체결량": 체결량,
                "현재가": 현재가,
                "단위체결가": 단위체결가,
                "단위체결량": 단위체결량,
                "당일매매수수료": 당일매매수수료,
                "당일매매세금": 당일매매세금,
            }
            self.strategy.save_chejan_event(chejan_event)

        elif gubun == "1": # 국내주식 잔고변경 시
            code = self.api.get_chejan_data(9001).replace("A", "").strip()
            종목명 = self.api.get_chejan_data(302).strip()
            주문체결시간 = self.api.get_chejan_data(908).strip()
            현재가 = int(self.api.get_chejan_data(10).replace('-', ''))
            보유수량 = int(self.api.get_chejan_data(930).strip())
            매입단가 = int(self.api.get_chejan_data(931).strip())
            주문가능수량 = int(self.api.get_chejan_data(933).strip())
            매도매수구분 = self.api.get_chejan_data(946).strip()
            손익률 = self.api.get_chejan_data(8019).strip()
            당일실현손익 = int(self.api.get_chejan_data(990).strip())
            당일매매수수료 = 0 if len(self.api.get_chejan_data(938)) == 0 else int(self.api.get_chejan_data(938))
            당일매매세금 = 0 if len(self.api.get_chejan_data(939)) == 0 else int(self.api.get_chejan_data(939))

            chejan_event = {
                "구분": gubun,
                "종목코드": code,
                "종목명": 종목명,
                "주문체결시간": 주문체결시간,
                "현재가": 현재가,
                "보유수량": 보유수량,
                "매입단가": 매입단가,
                "주문가능수량": 주문가능수량,
                "매도매수구분": 매도매수구분,
                "손익률": 손익률,
                "당일실현손익": 당일실현손익,
                "당일매매수수료": 당일매매수수료,
                "당일매매세금": 당일매매세금,
            }
            self.strategy.save_chejan_event(chejan_event)

    def _on_api_receive_real_data(self, code: str, real_type: str, real_data):
        if real_type == "주식체결":
            try:
                현재가 = int(self.api.get_comm_real_data(code, 10).replace('-', ''))  # "+-n": str
                등락률 = float(self.api.get_comm_real_data(code, 12).strip()) # "+-n.nn": str
                체결시간 = self.api.get_comm_real_data(code, 20)  # "HHMMSS": str
            except:
                return

            if code and 현재가 and (등락률 is not None) and 체결시간:
                market_event = {
                    "종목코드": code,
                    "현재가": 현재가,
                    "등락률": 등락률,
                    "체결시간": 체결시간,
                }
                self.strategy.save_market_event(market_event)

        elif real_type == "주식우선호가":
            pass

        elif real_type == "주식호가잔량":
            pass

    def _on_api_receive_condition_ver(self, ret, msg):
        pass

    def _on_api_receive_tr_condition(self, scr_no, code_price, condition_name, index, next_flag):
        pass

    def _on_api_receive_real_condition(self, code, event_type, condition_name, condition_index):
        pass

    def _on_api_receive_msg(self, scr_no, rq_name, tr_code, msg):
        self.ui.show_api_message(msg)
        self.notifier.send_msg(msg)
        self.logger.store_event_log(msg)

    # ---------------------------------------------------------------------
    # ui -> controller
    # ---------------------------------------------------------------------
    def _on_ui_auto_trade_toggled(self, checked: bool):
        self.ui.toggle_ctrl(checked) # ui에서 버튼 바꾸기
        if checked:
            if self.queue.resume("order"):
                self.ui.show_app_message("order queue 재개")
            if self.queue.resume("tr"):
                self.ui.show_app_message("tr queue 재개")
        else:
            if self.queue.pause("order"):
                self.ui.show_app_message("order queue 중지")
            if self.queue.pause("tr"):
                self.ui.show_app_message("tr queue 중지")

    # ---------------------------------------------------------------------
    # queue -> controller
    # ---------------------------------------------------------------------
    def _on_queue_request(self, request: dict):
        dispatch = {
            "send_order": self.api.send_order,
            "send_condition": self.api.send_condition,
            "comm_rq_data": self.api.comm_rq_data,
            "comm_kw_rq_data": self.api.comm_kw_rq_data,
            "comm_condition_load": self.api.comm_condition_load,
        }
        method = request.get("method")

        if method == "comm_rq_data":
            for id_, value in request.get("setinput").items():
                self.api.set_input_value(id_, value)
        fn = dispatch.get(method)
        if not fn:
            self.ui.show_app_message(f"지원하지 않는 요청: {method}")
            return

        fn(**(request.get("kwargs")))

    def _on_queue_left_count(self, queue_name: str, left_count: int):
        self.ui.queue_state(queue_name, left_count)

    # ---------------------------------------------------------------------
    # strategy -> controller
    # ---------------------------------------------------------------------
    def _on_strategy_order_request(self, payload: dict):
        name = "order" # settings/request_limit와 일치시키기
        payload["kwargs"]["rq_name"] = "order"
        payload["kwargs"]["screen_no"] = self.screen_manager.get_screen()
        payload["kwargs"]["acc_no"] = self.account_num
        self.queue.enqueue(name, payload)

    def _on_strategy_tr_request(self, payload: dict):
        name = "tr" # settings/request_limit
        if "screen_no" in payload.get("kwargs"):
            payload["kwargs"]["screen_no"] = self.screen_manager.get_screen()
        if "acc_no" in payload.get("kwargs"):
            payload["kwargs"]["acc_no"] = self.account_num
        if "계좌번호" in payload.get("setinput"):
            payload["setinput"]["계좌번호"] = self.account_num
        self.queue.enqueue(name, payload)

    def _on_strategy_realtime_request(self, payload: dict):
        code_list = payload.get("code_list")
        fid_list = payload.get("fid_list")
        self.subscribe_realtime(code_list, fid_list)

    def _on_strategy_alert(self, msg: str):
        self.ui.show_app_message(msg)
        self.notifier.send_msg(msg)
        self.logger.store_event_log(msg)

#-----------------------------------------------------------------------------------------------------------------------

    def login(self): # 로그인 요청
        self.api.comm_connect()

    def check_connection(self) -> bool: # 연결상태를 확인
        return self.api.get_connect_state() == 1

    def connection_state_to_ui(self): # 연결상태를 ui에 표시(1초마다)
        self.ui.connection_state(self.check_connection())

    def balance_info(self): # 계좌번호
        login_dict = self.api.get_login_info() # 로그인 정보 가져오기
        acc_idx = self.settings.get("account_index") # settings_cfg에서 몇번째 계좌로 할 지 읽어오기
        self.account_num = login_dict.get("acc_list")[acc_idx] # 그 인덱스로 self.account_num 설정

    def subscribe_realtime(self, code_list: str, fid_list: str):
        screen_no = self.screen_manager.get_screen()
        code_list = code_list
        fid_list = fid_list
        real_type = "1" # 추가등록
        self.api.set_real_reg(screen_no, code_list, fid_list, real_type)
