from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QObject, pyqtSignal


class KiwoomAPI(QObject):
    on_event_connect = pyqtSignal(int)
    on_receive_tr_data = pyqtSignal(str, str, str, str, str)
    on_receive_chejan_data = pyqtSignal(str, int, str)
    on_receive_real_data = pyqtSignal(str, str, str)
    on_receive_condition_ver = pyqtSignal(int, str)
    on_receive_tr_condition = pyqtSignal(str, str, str, int, int)
    on_receive_real_condition = pyqtSignal(str, str, str, str)
    on_receive_msg = pyqtSignal(str, str, str, str)

    def __init__(self):
        super().__init__()
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")

        self.kiwoom.OnEventConnect.connect(self._on_event_connect)
        self.kiwoom.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.kiwoom.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        self.kiwoom.OnReceiveRealData.connect(self._on_receive_real_data)
        self.kiwoom.OnReceiveConditionVer.connect(self._on_receive_condition_ver)
        self.kiwoom.OnReceiveTrCondition.connect(self._on_receive_tr_condition)
        self.kiwoom.OnReceiveRealCondition.connect(self._on_receive_real_condition)
        self.kiwoom.OnReceiveMsg.connect(self._on_receive_msg)

#-----------------------------------------------------------------------------------------------------------------------
    def set_input_value(self, id_: str, value:str):
        """TR요청을 위한 파라미터 설정"""
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", id_, value)

    def set_real_reg(self, screen_no: str, code_list: str, fid_list: str, real_type: str):
        """여러종목 실시간 시세 등록 요청(요청 제한 포함 x)"""
        self.kiwoom.dynamicCall(
            "SetRealReg(QString, QString, QString, QString)",
            screen_no, code_list, fid_list, real_type
        )
        # ex) code_list = "005930;000660;035420"
        # ex) fid_list = "10;12;20;41"
        # real_type "0": 기존것을 지우고 등록, "1": 추가 등록

#-----------------------------------------------------------------------------------------------------------------------
    def send_order(
            self, rq_name: str, screen_no: str, acc_no: str, order_type: int, code: str, qty: int,
            price: int, hoga_gb: str, org_order_no: str
    ):
        """주문 요청"""
        code = code[:6] # 넥스트레이드도 기존 6자리 종목코드 사용
        self.kiwoom.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            [rq_name, screen_no, acc_no, order_type, code, qty, price, hoga_gb, org_order_no]
        )
        # order_type: { 1=신규매수, 2=신규매도, 3=매수취소, 4=매도취소, 5=매수정정, 6=매도정정 }
        #             { 11 : SOR매수, 12 : SOR매도, 13 : SOR취소, 15 : SOR정정 }
        # hoga_gb: "00"=지정가, "03"=시장가(price = 0), "29"=중간가
        # org_order_no: 신규주문은 "", 정정/취소는 원주문번호

    def send_condition(self, screen_no, condition_name, idx, search):
        """조건검색 실행 요청"""
        self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)", screen_no, condition_name, idx, search)

    def comm_connect(self):
        """로그인 연결 요청"""
        self.kiwoom.dynamicCall("CommConnect()")

    def comm_rq_data(self, rq_name: str, tr_code: str, prev_next: int, screen_no: str):
        """TR 요청"""
        # prev_next: 0=단일조회, 2=연속조회
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", rq_name, tr_code, prev_next, screen_no)

    def comm_kw_rq_data(self, arr_code: str, next_: int, code_count: int, type_flag: int, rq_name: str, screen_no: str):
        """100종목까지 조회할 수 있는 복수종목 조회함수"""
        self.kiwoom.dynamicCall(
            "CommKwRqData(QString, int, int, int, QString, QString)",
            [arr_code, next_, code_count, type_flag, rq_name, screen_no]
        )
        # arr_code: 종목코드 리스트, next_: 0만 가능, code_count: 종목코드 개수, type_flag: { 0=주식, 3=선물 }

    def comm_condition_load(self):
        """조건식 목록 요청"""
        self.kiwoom.dynamicCall("GetConditionLoad()")

#-----------------------------------------------------------------------------------------------------------------------
    def get_comm_data(self, tr_code, record_name, index, item_name):
        """수신한 TR데이터 조회"""
        return self.kiwoom.dynamicCall(
            "GetCommData(QString, QString, int, QString)", tr_code, record_name, index, item_name
        )

    def get_repeat_cnt(self, tr_code, rq_name):
        """반복 데이터 횟수 조회"""
        return self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name)

    def get_chejan_data(self, fid):
        """체결/잔고 수신 데이터 조회"""
        return self.kiwoom.dynamicCall("GetChejanData(int)", fid)

    def get_comm_real_data(self, code, fid):
        """실시간 수신 데이터 조회"""
        return self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, fid)

    def get_condition_name_list(self):
        """조건식 목록 조회"""
        return self.kiwoom.dynamicCall("GetConditionNameList()").rstrip(';').split(';')

    def get_connect_state(self):
        """접속 상태 조회"""
        return self.kiwoom.dynamicCall("GetConnectState()") # 1:연결, 0:연결안됨

    def get_login_info(self) -> dict:
        """로그인 정보 조회"""
        login_info = {"account_cnt": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCOUNT_CNT"),
                      "acc_list": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCLIST").rstrip(';').split(';'),
                      "user_id": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "USER_ID"),
                      "user_name": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "USER_NAME"),
                      "server_gb": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "GetServerGubun"), # "1" 모의
                      "key_sec": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "KEY_BSECGB"),
                      "firew_sec": self.kiwoom.dynamicCall("GetLoginInfo(QString)", "FIREW_SECGB"),
                      }
        return login_info

#-----------------------------------------------------------------------------------------------------------------------
    def _on_event_connect(self, err_code):
        self.on_event_connect.emit(err_code)

    def _on_receive_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next):
        self.on_receive_tr_data.emit(scr_no, rq_name, tr_code, record_name, prev_next)

    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        self.on_receive_chejan_data.emit(gubun, item_cnt, fid_list)
        # gubun: { 0=접수와체결시, 1=국내주식잔고변경시, 4=파생잔고변경시 }

    def _on_receive_real_data(self, code, real_type, real_data):
        self.on_receive_real_data.emit(code, real_type, real_data)

    def _on_receive_condition_ver(self, ret, msg):
        self.on_receive_condition_ver.emit(ret, msg)

    def _on_receive_tr_condition(self, scr_no, code_price, condition_name, index, next_flag):
        self.on_receive_tr_condition.emit(scr_no, code_price, condition_name, index, next_flag)

    def _on_receive_real_condition(self, code, event_type, condition_name, condition_index):
        self.on_receive_real_condition.emit(code, event_type, condition_name, condition_index)

    def _on_receive_msg(self, scr_no, rq_name, tr_code, msg):
        msg = msg.strip()
        self.on_receive_msg.emit(scr_no, rq_name, tr_code, msg)