from datetime import datetime, timedelta

connected_clients = {}  # 存儲連接的client
recording_devices = {}  # 存儲連接的錄音設備(edge)
device_schedules = {}  # 每個設備的排程信息


class RecordingSchedule:
    def __init__(self, interval, duration, count=None):
        self.interval = interval  # 間隔時間（分鐘）
        self.duration = duration  # 單次錄製時長（秒）
        self.count = count  # 錄製次數（None 表示無限次）
        self.current_count = 0  # 當前已錄製次數
        self.next_recording_time = datetime.now() + timedelta(minutes=interval)

    def update_next_recording_time(self):
        self.next_recording_time = datetime.now() + timedelta(minutes=self.interval)

    def increment_count(self):
        self.current_count += 1

    def is_completed(self):
        return self.count is not None and self.current_count >= self.count
        # self.count is None | self.current_count >= self.count
        # 0 | 0 => 1 | 0 => false
        # 0 | 1 => 1 | 1 => True (啟動計數上限 且 當前次數 >= 計數上限 ==> 當前錄音排程執行完畢)
        # 1 | 0 => 0 | 0 => false
        # 1 | 1 => 0 | 1 => false
