import requests
import os

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


def download_recording(recording):
    """
    下載單個錄音
    """
    recording_id = recording['id']
    filename = recording['filename']

    response = requests.get(f"{SERVER_URL}/download/{recording_id}", stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"成功下載錄音: {filename}")
    else:
        print(f"下載錄音失敗 ID: {recording_id}。錯誤: {response.text}")


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
