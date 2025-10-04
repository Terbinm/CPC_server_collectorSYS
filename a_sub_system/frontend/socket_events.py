from flask import request
from flask_main import socketio
from shared_state import connected_clients, recording_devices, device_schedules
import uuid
import logging
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# 追蹤排程檢查器是否已經在運行的標誌
schedule_checker_running = False
schedule_checker_lock = Lock()

# 用於防止重複執行的鎖
execution_locks = {}


@socketio.on('connect')
def handle_connect():
    """
    處理客戶端連接事件
    """
    try:
        logger.info(f"客戶端已連接。SID: {request.sid}")
        socketio.emit('update_devices', {'devices': list(recording_devices.values())})

        # 如果排程檢查器尚未運行,則啟動它
        global schedule_checker_running
        with schedule_checker_lock:
            if not schedule_checker_running:
                socketio.start_background_task(schedule_checker)
                schedule_checker_running = True
                logger.info("已啟動排程檢查器背景任務")
    except Exception as e:
        logger.error(f"處理連接事件時出錯: {str(e)}")


@socketio.on('register_device')
def handle_register_device(data):
    """
    處理設備註冊事件

    :param data: 包含客戶端ID和設備名稱的字典
    """
    try:
        client_id = data['client_id']
        device_name = data['device_name']
        if client_id in recording_devices:
            recording_devices[client_id]['status'] = 'IDLE'
            recording_devices[client_id]['name'] = device_name
        else:
            recording_devices[client_id] = {'id': client_id, 'name': device_name, 'status': 'IDLE'}
        connected_clients[request.sid] = {'id': client_id, 'type': 'device'}
        socketio.emit('update_devices', {'devices': list(recording_devices.values())})
        logger.info(f"設備已註冊或重新連接。ID: {client_id}, 名稱: {device_name}")
    except Exception as e:
        logger.error(f"處理設備註冊時出錯: {str(e)}")


@socketio.on('disconnect')
def handle_disconnect():
    """
    處理客戶端斷開連接事件
    """
    try:
        client_data = connected_clients.pop(request.sid, None)
        if client_data:
            device_id = client_data['id']
            if device_id in recording_devices:
                recording_devices[device_id]['status'] = 'OFFLINE'
                socketio.emit('update_devices', {'devices': list(recording_devices.values())})
            logger.info(f"客戶端已斷開連接。ID: {device_id}")
    except Exception as e:
        logger.error(f"處理斷開連接事件時出錯: {str(e)}")


@socketio.on('request_id')
def handle_request_id():
    """
    處理客戶端請求新ID的事件
    """
    try:
        client_id = str(uuid.uuid4())
        connected_clients[request.sid] = {'id': client_id, 'type': 'device'}
        socketio.emit('assign_id', {'client_id': client_id})
        logger.info(f"為客戶端分配了新ID: {client_id}")
    except Exception as e:
        logger.error(f"處理ID請求時出錯: {str(e)}")


@socketio.on('update_status')
def handle_update_status(data):
    """
    處理設備狀態更新事件

    :param data: 包含設備ID和新狀態的字典
    """
    try:
        device_id = data['device_id']
        status = data['status']
        if device_id in recording_devices:
            recording_devices[device_id]['status'] = status
            socketio.emit('update_devices', {'devices': list(recording_devices.values())})
            logger.info(f"已更新設備 {device_id} 的狀態: {status}")
    except Exception as e:
        logger.error(f"處理狀態更新時出錯: {str(e)}")


@socketio.on('start_recording')
def handle_start_recording(data):
    """
    處理開始錄音事件

    :param data: 包含設備ID和錄音持續時間的字典
    :return: 包含錄音信息或錯誤信息的字典
    """
    try:
        device_id = data['device_id']
        duration = data.get('duration', 10)
        if device_id in recording_devices:
            socketio.emit('record', {'duration': duration},
                          room=next(sid for sid, client in connected_clients.items() if client['id'] == device_id))
            logger.info(f"開始錄音 (設備 ID: {device_id}, 持續時間: {duration}秒)")
            return {'message': f'開始錄音 (設備 ID: {device_id})', 'duration': duration}
        else:
            logger.warning(f"嘗試在未註冊的設備上開始錄音: {device_id}")
            return {'error': '設備未找到'}
    except Exception as e:
        logger.error(f"處理開始錄音事件時出錯: {str(e)}")
        return {'error': '錄音開始失敗'}


@socketio.on('update_device_name')
def handle_update_device_name(data):
    """
    處理更新設備名稱的事件

    :param data: 包含設備ID和新設備名稱的字典
    """
    try:
        device_id = data['device_id']
        new_name = data['device_name']
        if device_id in recording_devices:
            recording_devices[device_id]['name'] = new_name
            socketio.emit('update_devices', {'devices': list(recording_devices.values())})
            logger.info(f"已更新設備 {device_id} 的名稱: {new_name}")
        else:
            logger.warning(f"嘗試更新未註冊設備的名稱: {device_id}")
    except Exception as e:
        logger.error(f"更新設備名稱時出錯: {str(e)}")


###########################
#         排程功能         #
###########################
def check_and_execute_schedules():
    """
    檢查並執行所有設備的排程
    """
    debug_count = 0
    current_time = datetime.now()
    for device_id, schedule in list(device_schedules.items()):
        # 為每個設備創建一個鎖(如果還沒有)
        if device_id not in execution_locks:
            execution_locks[device_id] = Lock()

        # 嘗試獲取鎖，如果無法獲取，則跳過這個設備(避免重複呼叫)
        if not execution_locks[device_id].acquire(blocking=False):
            logger.debug(
                f"設備 {device_id} 的排程正在執行中，跳過 --- {len(list(device_schedules.items()))} / {debug_count}")
            continue

        try:
            if current_time >= schedule.next_recording_time:

                # 執行錄音
                socketio.emit('record', {'duration': schedule.duration},
                              room=next(sid for sid, client in connected_clients.items() if client['id'] == device_id))

                # 更新排程
                logger.debug(f"設備 {device_id} 新增一次前，錄音紀錄---{schedule.current_count}")
                schedule.increment_count()
                schedule.update_next_recording_time()
                logger.debug(f"設備 {device_id} 新增一次後，錄音紀錄---{schedule.current_count}")

                if schedule.is_completed():
                    del device_schedules[device_id]
                    logger.info(f"設備 {device_id} 的排程已完成並被刪除")
                else:
                    logger.info(f"設備 {device_id} 執行了排程錄音，下次錄音時間: {schedule.next_recording_time}")

                # 發送更新通知
                socketio.emit('update_devices', {'devices': list(recording_devices.values())})
                socketio.emit('new_recording', {
                    'device_id': device_id,
                    'timestamp': current_time.isoformat(),
                    'duration': schedule.duration
                })

        finally:
            # 釋放鎖
            execution_locks[device_id].release()


def schedule_checker():
    global schedule_checker_running
    try:
        while True:
            check_and_execute_schedules()
            socketio.sleep(1)  # 每秒檢查一次
    finally:
        with schedule_checker_lock:
            schedule_checker_running = False
        logger.info("排程檢查器已停止")