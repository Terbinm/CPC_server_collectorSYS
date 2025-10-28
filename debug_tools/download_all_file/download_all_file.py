import requests, os, time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, Timeout

SERVER_URL = 'http://163.18.22.51:88'
DOWNLOAD_DIR = "downloaded_recordings"

# 建立一個全域 Session，帶重試策略
_session = requests.Session()
_retries = Retry(
    total=3,                # 總重試次數（含 read/連線/狀態碼）
    connect=3,
    read=3,
    backoff_factor=1.0,     # 1, 2, 4 秒… 指數退避
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
_session.mount("http://", HTTPAdapter(max_retries=_retries))
_session.mount("https://", HTTPAdapter(max_retries=_retries))

def get_all_recordings():
    try:
        r = _session.get(f"{SERVER_URL}/recordings", timeout=(5, 10))
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"獲取錄音列表失敗：{e}")
        return []

def download_recording(
    recording,
    connect_timeout=5,
    read_timeout=8,         # 單次讀取逾時短一點，便於偵測卡住
    overall_timeout=60*20,  # 單檔上限時間
    stall_timeout=30,       # 兩次進度間隔不可超過
    max_stall_retries=5,    # 連續續傳最多 5 次
    chunk_size=64 * 1024    # 64 KB，增加進度回報頻率
):
    import time
    recording_id = recording["id"]
    filename = recording["filename"]

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    dst = os.path.join(DOWNLOAD_DIR, filename)
    tmp = dst + ".part"
    url = f"{SERVER_URL}/download/{recording_id}"

    print(f"開始下載：{filename} (id={recording_id})")

    start_t = time.monotonic()
    last_progress_t = start_t
    bytes_written = 0
    expected_total = None

    # 若上次有殘留 .part，從其大小續傳
    if os.path.exists(tmp):
        bytes_written = os.path.getsize(tmp)

    stall_retries = 0

    def open_stream(resume_from):
        headers = {"Accept-Encoding": "identity"}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
        resp = _session.get(
            url, stream=True, timeout=(connect_timeout, read_timeout), headers=headers
        )
        resp.raise_for_status()
        # 取得 Content-Length（若是 206 則為剩餘長度）
        cl = resp.headers.get("Content-Length")
        if cl is not None:
            try:
                return resp, int(cl)
            except ValueError:
                return resp, None
        return resp, None

    try:
        # 先開檔（append 模式，續傳時直接接著寫）
        with open(tmp, "ab") as f:
            resp, this_len = open_stream(bytes_written)
            # 如果是第一次開，估一下總長
            if bytes_written == 0:
                expected_total = this_len
            else:
                # 續傳時 expected_total 只能用「已寫 + 剩餘」來估
                if this_len is not None:
                    expected_total = bytes_written + this_len

            while True:
                # 整體時間限制
                if time.monotonic() - start_t > overall_timeout:
                    raise Timeout(f"超過整體下載時限 {overall_timeout}s")

                try:
                    progressed = False
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)
                            progressed = True
                            now = time.monotonic()
                            if now - last_progress_t >= 2:
                                if expected_total:
                                    pct = bytes_written * 100 / expected_total
                                    speed = bytes_written / (now - start_t + 1e-9)
                                    print(f"  進度：{pct:.1f}%  已收:{bytes_written}  速率:{speed/1024/1024:.2f} MB/s")
                                else:
                                    speed = bytes_written / (now - start_t + 1e-9)
                                    print(f"  已收:{bytes_written} bytes  速率:{speed/1024/1024:.2f} MB/s")
                                last_progress_t = now
                            # 若有進度就重置 stall 計數
                            stall_retries = 0

                        # 無進度監測（例如伺服器在 chunk 邊界卡住）
                        if time.monotonic() - last_progress_t > stall_timeout:
                            raise Timeout(f"{stall_timeout}s 無進度，準備續傳")

                    # for 走完 → 代表伺服器關閉串流（下載可能完成）
                    break

                except (requests.exceptions.ReadTimeout, Timeout):
                    # 讀取逾時或長時間無進度：重新打開連線續傳
                    stall_retries += 1
                    if stall_retries > max_stall_retries:
                        raise Timeout(f"續傳已超過 {max_stall_retries} 次，放棄此檔")
                    print(f"  偵測到卡住，嘗試續傳第 {stall_retries}/{max_stall_retries} 次（已收 {bytes_written} bytes）")
                    try:
                        resp.close()
                    except Exception:
                        pass
                    # 重新開流，從目前位移續傳
                    resp, this_len = open_stream(bytes_written)
                    if expected_total is None and this_len is not None:
                        expected_total = bytes_written + this_len
                    # 續傳重新計時進度
                    last_progress_t = time.monotonic()

        # 大小檢查（若知道總長）
        if expected_total is not None and bytes_written != expected_total:
            raise RequestException(f"大小不符：預期 {expected_total} 實得 {bytes_written}")

        os.replace(tmp, dst)
        print(f"成功下載：{dst}")
        return True

    except (Timeout, RequestException) as e:
        print(f"下載失敗（{filename}）：{e}")
    except Exception as e:
        print(f"下載異常（{filename}）：{e}")
    finally:
        # 若失敗，保留 .part 以便下次續傳（想自動清理就改成刪除）
        pass

    return False


def download_all_recordings():
    recs = get_all_recordings()
    if not recs:
        print("沒有找到任何錄音。")
        return
    print(f"找到 {len(recs)} 個錄音。")
    ok = 0
    for r in recs:
        ok += 1 if download_recording(r) else 0
    print(f"完成：成功 {ok}/{len(recs)}")

if __name__ == "__main__":
    download_all_recordings()
