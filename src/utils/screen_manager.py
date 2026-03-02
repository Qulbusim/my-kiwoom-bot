"""
키움 화면번호정책
- 화면번호 범위 0001~9999
- 화면번호 최대 200개 사용가능
- 한 화면번호당 100개 등록가능

기능
- 화면번호 받기
- 화면번호 방출
"""


class ScreenNumber:
    MAX_SCREEN_COUNT = 199 # 안전마진
    MAX_ITEMS_PER_SCREEN = 99 # 안전마진

    def __init__(self):
        # {화면번호: 현재 등록된 아이템 수}
        self._screens = {}

    def get_screen(self) -> str:
        """아이템을 등록할 수 있는 화면번호를 반환"""
        # 1. 기존 화면번호가 사용 가능한 경우
        for screen, count in self._screens.items():
            if count < self.MAX_ITEMS_PER_SCREEN:
                self._screens[screen] += 1
                return screen

        # 2. 기존 화면번호의 아이템이 가득 찬 경우, 새 화면번호 발급
        if len(self._screens) < self.MAX_SCREEN_COUNT:
            for i in range(1000, 10000):
                screen = str(i)
                if screen not in self._screens:
                    self._screens[screen] = 1
                    return screen

        # 3. 199개를 모두 사용 중이고 모든 화면이 꽉 찬 경우
        raise RuntimeError(f"최대 화면 개수({self.MAX_SCREEN_COUNT}) 초과")

    def release_screen(self, screen: str) -> None:
        """화면번호에서 아이템 하나를 제거하고, 아이템이 0개가 되면 화면을 방출"""
        screen = str(screen) # 에러방지
        if screen in self._screens:
            self._screens[screen] -= 1
            # 아이템이 하나도 없으면 딕셔너리에서 제거
            if self._screens[screen] <= 0:
                self._screens.pop(screen)