import datetime
from collections import deque

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


class RequestQueue(QObject):
    """
    settings에서 종류별 시간제한을 받아와서 종류별 BabyQueue 인스턴스 생성
    종류 이름과 요청을 넣어 enqueue()로 실행

    BabyQueue에서 전달받은 요청객체와 남은 요청 수, 큐 이름을 emit
    """
    to_caller_signal = pyqtSignal(dict)
    left_req_num = pyqtSignal(str, int)

    def __init__(self, settings):
        super().__init__()
        self.queues = {}

        for name, limits in settings["request_limit"].items():
            max_per_sec = limits.get("max_per_sec")
            max_per_min = limits.get("max_per_min")
            max_per_hour = limits.get("max_per_hour")
            self.queues[name] = BabyQueue(name, max_per_sec, max_per_min, max_per_hour)
            self.queues[name].deliver_item.connect(self._deliver_to_caller)
            self.queues[name].left_request.connect(self._deliver_left_req_num)

    def enqueue(self, name: str, request: dict) -> None:
        if self.queues.get(name):
            self.queues.get(name).enqueue(request)

    def pause(self, name: str) -> bool:
        if self.queues.get(name):
            self.queues.get(name).pause()
            return True
        return False

    def resume(self, name: str) -> bool:
        if self.queues.get(name):
            self.queues.get(name).resume()
            return True
        return False

    def _deliver_to_caller(self, item) -> None:
        self.to_caller_signal.emit(item)

    def _deliver_left_req_num(self, name, num) -> None:
        self.left_req_num.emit(name, num)


class BabyQueue(QObject):
    """
    enqueue 시 즉시 dequeue를 시도
    시간 제한으로 남은 요청은 1초마다 가능한 만큼 dequeue

    dequeue된 객체는 pyqtSignal로 전달
    큐에 남은 요청 수는 큐 이름과 함께 pyqtSignal로 emit
    """
    deliver_item = pyqtSignal(dict)
    left_request = pyqtSignal(str, int) # queue_name, left_request_num

    def __init__(self, queue_name, max_per_sec, max_per_min, max_per_hour):
        super().__init__()
        self._item = deque()
        self.queue_name = queue_name
        self.time_limit = TimeLimit(max_per_sec, max_per_min, max_per_hour)
        self._enabled = True

        self.timer = QTimer()
        self.timer.timeout.connect(self._check_state)
        self.timer.start(1000) # ms

    def enqueue(self, request: dict) -> None:
        self._item.append(request)
        self._dequeue()

    def _dequeue(self) -> None:
        if self._item and self.time_limit.can_send() and self._enabled:
            self.time_limit.mark_sent()
            self.deliver_item.emit(self._item.popleft())

    def _check_state(self) -> None:
        while self._item and self.time_limit.can_send() and self._enabled:
            self._dequeue()
        self._how_many_req()

    def _how_many_req(self) -> None:
        left_request_num = len(self._item)
        self.left_request.emit(self.queue_name, left_request_num)

    def pause(self) -> None:
        self._enabled = False

    def resume(self) -> None:
        self._enabled = True
        self._check_state()


class TimeLimit:
    """
    - can_send(): 전송 가능 여부 검사
    - mark_sent(): 전송 시각 기록

    단일 큐 관리자를 쓸 때만 사용
    """
    def __init__(self, max_per_sec=None, max_per_min=None, max_per_hour=None):
        self.max_per_sec = max_per_sec
        self.max_per_min = max_per_min
        self.max_per_hour = max_per_hour

        active_limits = [v for v in (max_per_sec, max_per_min, max_per_hour) if v is not None]
        history_size = max(active_limits) if active_limits else None
        self.last_send_times = deque(maxlen=history_size)

    def can_send(self) -> bool:
        now = datetime.datetime.now()

        if self.max_per_sec is not None:
            if len(self.last_send_times) >= self.max_per_sec:
                if now - self.last_send_times[-self.max_per_sec] < datetime.timedelta(seconds=1):
                    return False

        if self.max_per_min is not None:
            if len(self.last_send_times) >= self.max_per_min:
                if now - self.last_send_times[-self.max_per_min] < datetime.timedelta(minutes=1):
                    return False

        if self.max_per_hour is not None:
            if len(self.last_send_times) >= self.max_per_hour:
                if now - self.last_send_times[-self.max_per_hour] < datetime.timedelta(hours=1):
                    return False

        return True

    def mark_sent(self) -> None:
        self.last_send_times.append(datetime.datetime.now())