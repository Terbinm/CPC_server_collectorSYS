import requests
import os
from requests.exceptions import RequestException, Timeout

# 設置服務器 URL
SERVER_URL = 'http://163.18.22.51:88'


# SERVER_URL = 'http://192.168.201.31:5000'


def get_all_recordings():
    """
    獲取所有錄音的列表
    """
    response = requests.get(f"{SERVER_URL}/recordings")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"獲取錄音列表失敗。錯誤: {response.text}")
        return []


def download_recording(recording, timeout=30, max_retries=3):
    """
    下載單個錄音，包含超時處理和重試機制

    Args:
        recording (dict): 包含錄音資訊的字典
        timeout (int): 請求超時時間（秒）
        max_retries (int): 最大重試次數
    """
    recording_id = recording['id']
    filename = recording['filename']

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{SERVER_URL}/download/{recording_id}",
                                    stream=True,
                                    timeout=timeout)
            response.raise_for_status()  # 如果請求不成功則拋出異常

            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"成功下載錄音: {filename}")
            return  # 下載成功，退出函數

        except Timeout:
            print(f"下載錄音超時 ID: {recording_id}，嘗試次數: {attempt + 1}")
        except RequestException as e:
            print(f"下載錄音失敗 ID: {recording_id}，錯誤: {str(e)}，嘗試次數: {attempt + 1}")

        # 如果不是最後一次嘗試，則等待一段時間後重試
        if attempt < max_retries - 1:
            import time
            time.sleep(2 ** attempt)  # 指數退避策略

    print(f"下載錄音失敗 ID: {recording_id}，已達到最大重試次數")


def download_all_recordings():
    """
    下載所有錄音
    """
    recordings = get_all_recordings()
    if not recordings:
        print("沒有找到任何錄音。")
        return

    print(f"找到 {len(recordings)} 個錄音。")

    # 創建下載目錄
    download_dir = "downloaded_recordings"
    os.makedirs(download_dir, exist_ok=True)
    os.chdir(download_dir)

    for recording in recordings:
        download_recording(recording)

    print("所有錄音下載完成。")


if __name__ == "__main__":
    download_all_recordings()
