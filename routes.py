from flask import request, jsonify, send_file, render_template, redirect, url_for
from main import app, db, socketio
from models import AudioRecording
from utils import calculate_file_hash
from werkzeug.utils import secure_filename
import os
from shared_state import device_schedules, recording_devices, RecordingSchedule
import logging
import soundfile as sf
from io import BytesIO

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """
    宣傳首頁
    """
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """
    管理儀表板，顯示所有錄音和設備列表
    """
    try:
        recordings = AudioRecording.query.all()
        return render_template('dashboard.html', recordings=recordings, devices=list(recording_devices.values()))
    except Exception as e:
        logger.error(f"儀表板路由出錯: {str(e)}")
        return jsonify({"error": "內部伺服器錯誤"}), 500


@app.route('/upload_recording', methods=['POST'])
def upload_recording():
    """
    處理錄音檔案上傳（支援邊緣設備和網路上傳）
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': '沒有檔案部分'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '沒有選擇檔案'}), 400

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # 判斷是網路上傳還是設備上傳
            device_id = request.form.get('device_id', 'WEB_UPLOAD')

            # 獲取或計算 duration
            duration = request.form.get('duration')
            if duration:
                duration = float(duration)
            else:
                # 網路上傳時自動計算音檔時長
                try:
                    audio_info = sf.info(file_path)
                    duration = audio_info.duration
                except Exception as e:
                    logger.warning(f"無法讀取音檔時長: {str(e)}")
                    duration = 0.0

            file_size = os.path.getsize(file_path)
            file_hash = calculate_file_hash(file_path)

            # 如果是設備上傳，驗證檔案完整性
            if device_id != 'WEB_UPLOAD':
                expected_size = int(request.form.get('file_size', 0))
                expected_hash = request.form.get('file_hash', '')

                if file_size != expected_size or file_hash != expected_hash:
                    os.remove(file_path)
                    return jsonify({'error': '檔案上傳不完整或已被修改'}), 400

            new_recording = AudioRecording(
                filename=filename,
                duration=duration,
                device_id=device_id,
                upload_complete=True,
                file_size=file_size,
                file_hash=file_hash
            )

            db.session.add(new_recording)
            db.session.commit()

            socketio.emit('new_recording', new_recording.to_dict(), namespace='/')

            logger.info(f"成功上傳錄音: {filename} (來源: {device_id})")
            return jsonify({'message': '檔案上傳成功', 'id': new_recording.id})
    except Exception as e:
        logger.error(f"上傳錄音時出錯: {str(e)}")
        return jsonify({'error': '檔案上傳失敗'}), 500


@app.route('/recordings', methods=['GET'])
def get_recordings():
    """
    獲取所有錄音的列表
    """
    try:
        recordings = AudioRecording.query.all()
        return jsonify([r.to_dict() for r in recordings])
    except Exception as e:
        logger.error(f"獲取錄音列表時出錯: {str(e)}")
        return jsonify({'error': '獲取錄音列表失敗'}), 500


@app.route('/download/<int:id>', methods=['GET'])
def download_recording(id):
    """
    下載指定ID的錄音檔案

    :param id: 錄音ID
    """
    try:
        recording = AudioRecording.query.get_or_404(id)
        if not recording.upload_complete:
            return jsonify({'error': '錄音尚未完成上傳，請稍後再試'}), 400
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], recording.filename),
                         as_attachment=True)
    except Exception as e:
        logger.error(f"下載錄音時出錯: {str(e)}")
        return jsonify({'error': '下載錄音失敗'}), 500


@app.route('/check_upload/<int:id>', methods=['GET'])
def check_upload(id):
    """
    檢查指定ID的錄音上傳狀態

    :param id: 錄音ID
    """
    try:
        recording = AudioRecording.query.get_or_404(id)
        return jsonify({'upload_complete': recording.upload_complete})
    except Exception as e:
        logger.error(f"檢查上傳狀態時出錯: {str(e)}")
        return jsonify({'error': '檢查上傳狀態失敗'}), 500


@app.route('/play/<int:id>', methods=['GET'])
def play_recording(id):
    """
    渲染播放指定ID錄音的頁面

    :param id: 錄音ID
    """
    try:
        recording = AudioRecording.query.get_or_404(id)
        return render_template('play.html', recording=recording)
    except Exception as e:
        logger.error(f"播放錄音時出錯: {str(e)}")
        return jsonify({'error': '播放錄音失敗'}), 500


@app.route('/delete/<int:id>', methods=['POST'])
def delete_recording(id):
    """
    刪除指定ID的錄音

    :param id: 錄音ID
    """
    try:
        recording = AudioRecording.query.get_or_404(id)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], recording.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(recording)
        db.session.commit()
        socketio.emit('recording_deleted', {'id': id})
        logger.info(f"成功刪除錄音: {recording.filename}")
        return jsonify({'message': '錄音已刪除'})
    except Exception as e:
        logger.error(f"刪除錄音時出錯: {str(e)}")
        return jsonify({'error': '刪除錄音失敗'}), 500


###########################
#         排程功能         #
###########################


@app.route('/schedule_management')
def schedule_management():
    """
    渲染排程管理頁面
    """
    devices = list(recording_devices.values())
    schedules = {device_id: schedule.__dict__ for device_id, schedule in device_schedules.items()}
    return render_template('schedule_management.html', devices=devices, schedules=schedules)


@app.route('/schedule', methods=['POST'])
def create_schedule():
    """
    創建新的錄音排程
    """
    try:
        data = request.json
        device_id = data.get('device_id')
        interval = float(data.get('interval'))  # 間隔時間（分鐘）
        duration = int(data.get('duration'))  # 單次錄製時長（秒）
        count = data.get('count')  # 錄製次數（可選）

        if device_id not in recording_devices:
            return jsonify({'error': '設備未找到'}), 404

        if device_id in device_schedules:
            return jsonify({'error': '該設備已有排程，請先刪除原有排程'}), 400

        schedule = RecordingSchedule(interval, duration, count)
        device_schedules[device_id] = schedule

        logger.info(f"為設備 {device_id} 創建了新的錄音排程")
        return jsonify({'message': '排程創建成功', 'next_recording': schedule.next_recording_time.isoformat()})
    except Exception as e:
        logger.error(f"創建排程時出錯: {str(e)}")
        return jsonify({'error': '創建排程失敗'}), 500


@app.route('/schedule/<device_id>', methods=['GET'])
def get_schedule(device_id):
    """
    獲取指定設備的排程信息
    """
    try:
        if device_id not in recording_devices:
            return jsonify({'error': '設備未找到'}), 404

        schedule = device_schedules.get(device_id)
        if not schedule:
            return jsonify({'message': '該設備沒有排程'})

        return jsonify({
            'interval': schedule.interval,
            'duration': schedule.duration,
            'count': schedule.count,
            'current_count': schedule.current_count,
            'next_recording': schedule.next_recording_time.isoformat()
        })
    except Exception as e:
        logger.error(f"獲取排程信息時出錯: {str(e)}")
        return jsonify({'error': '獲取排程信息失敗'}), 500


@app.route('/schedule/<device_id>', methods=['DELETE'])
def delete_schedule(device_id):
    """
    刪除指定設備的排程
    """
    try:
        if device_id not in recording_devices:
            return jsonify({'error': '設備未找到'}), 404

        if device_id in device_schedules:
            del device_schedules[device_id]
            logger.info(f"已刪除設備 {device_id} 的錄音排程")
            return jsonify({'message': '排程已刪除'})
        else:
            return jsonify({'message': '該設備沒有排程'})
    except Exception as e:
        logger.error(f"刪除排程時出錯: {str(e)}")
        return jsonify({'error': '刪除排程失敗'}), 500