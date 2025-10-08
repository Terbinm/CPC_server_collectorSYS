from flask import request, jsonify, send_file, render_template, Response
from flask_main import app, db, socketio, mongodb_handler
from models import AudioRecording, RecordingRepository
from utils import calculate_file_hash
from werkzeug.utils import secure_filename
import os
from shared_state import device_schedules, recording_devices, RecordingSchedule
import logging
import soundfile as sf
from io import BytesIO
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

# 初始化錄音資料存取層
recording_repo = RecordingRepository(mongodb_handler)


@app.route('/')
def index():
    """
    宣傳首頁
    """
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """
    管理儀表板,顯示所有錄音和設備列表
    """
    try:
        logger.info("正在載入儀表板...")

        # 獲取查詢參數
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        sort_by = request.args.get('sort_by',
                                   'time_desc')  # time_desc, time_asc, name_asc, name_desc, duration_desc, duration_asc

        # 限制 per_page 的範圍
        if per_page not in [10, 50, 100, 200, 1000]:
            per_page = 50

        # 確保 page 至少為 1
        if page < 1:
            page = 1

        # 設定排序方式
        sort_field = 'info_features.upload_time'
        sort_direction = -1  # -1 為降序（新到舊），1 為升序（舊到新）

        if sort_by == 'time_desc':
            sort_field = 'info_features.upload_time'
            sort_direction = -1
        elif sort_by == 'time_asc':
            sort_field = 'info_features.upload_time'
            sort_direction = 1
        elif sort_by == 'name_asc':
            sort_field = 'files.raw.filename'
            sort_direction = 1
        elif sort_by == 'name_desc':
            sort_field = 'files.raw.filename'
            sort_direction = -1
        elif sort_by == 'duration_desc':
            sort_field = 'info_features.duration'
            sort_direction = -1
        elif sort_by == 'duration_asc':
            sort_field = 'info_features.duration'
            sort_direction = 1

        # 計算總數
        total_count = recording_repo.count()
        total_pages = (total_count + per_page - 1) // per_page  # 向上取整

        # 計算跳過的記錄數
        skip = (page - 1) * per_page

        # 從資料庫獲取分頁資料
        try:
            documents = recording_repo.collection.find().sort(sort_field, sort_direction).skip(skip).limit(per_page)
            recordings = [AudioRecording.from_mongodb_document(doc) for doc in documents]
            logger.info(f"查詢到 {len(recordings)} 筆錄音記錄 (第 {page} 頁，共 {total_pages} 頁，總計 {total_count} 筆)")
        except Exception as e:
            logger.error(f"查詢錄音記錄失敗: {e}")
            recordings = []

        # 轉換為字典格式以便模板使用,包含分析狀態
        recordings_dict = []
        for idx, rec in enumerate(recordings):
            try:
                rec_dict = rec.to_dict()

                # 計算當前記錄在整體列表中的索引位置
                rec_dict['display_index'] = skip + idx + 1

                # 獲取分析狀態和摘要
                original_doc = recording_repo.collection.find_one({"AnalyzeUUID": rec.analyze_uuid})
                if original_doc:
                    rec_dict['analysis_status'] = original_doc.get('analysis_status', 'pending')
                    rec_dict['current_step'] = original_doc.get('current_step', 0)

                    # 獲取分析摘要,並計算百分比
                    analysis_summary = original_doc.get('analysis_summary', {})
                    if analysis_summary and 'total_segments' in analysis_summary:
                        total = analysis_summary.get('total_segments', 0)
                        normal = analysis_summary.get('normal_count', 0)
                        abnormal = analysis_summary.get('abnormal_count', 0)

                        # 確保所有計數欄位都存在
                        analysis_summary['normal_count'] = normal
                        analysis_summary['abnormal_count'] = abnormal
                        analysis_summary['total_segments'] = total

                        # 計算百分比
                        analysis_summary['normal_percentage'] = (normal / total * 100) if total > 0 else 0
                        analysis_summary['abnormal_percentage'] = (abnormal / total * 100) if total > 0 else 0

                    rec_dict['analysis_summary'] = analysis_summary
                else:
                    rec_dict['analysis_status'] = 'pending'
                    rec_dict['current_step'] = 0
                    rec_dict['analysis_summary'] = {}

                recordings_dict.append(rec_dict)
                logger.debug(f"錄音 {idx + 1} 轉換成功: {rec_dict.get('filename')}")
            except Exception as e:
                logger.error(f"錄音 {idx + 1} 轉換失敗: {e}")
                continue

        logger.info(f"成功轉換 {len(recordings_dict)} 筆錄音記錄")

        # 計算分頁資訊
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
            'start_index': skip + 1,
            'end_index': min(skip + per_page, total_count),
            'sort_by': sort_by
        }

        return render_template('dashboard.html',
                               recordings=recordings_dict,
                               devices=list(recording_devices.values()),
                               pagination=pagination)
    except Exception as e:
        logger.error(f"儀表板路由出錯: {str(e)}", exc_info=True)
        return jsonify({"error": "內部伺服器錯誤", "detail": str(e)}), 500


@app.route('/upload_recording', methods=['POST'])
def upload_recording():
    """
    處理錄音檔案上傳(支援邊緣設備和網路上傳) - 使用 GridFS
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': '沒有檔案部分'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '沒有選擇檔案'}), 400

        if file:
            filename = secure_filename(file.filename)

            # 判斷是網路上傳還是設備上傳
            device_id = request.form.get('device_id', 'WEB_UPLOAD')

            # 讀取檔案內容
            file_data = file.read()
            file_size = len(file_data)

            # 計算檔案 hash
            import hashlib
            file_hash = hashlib.sha256(file_data).hexdigest()

            # 如果是設備上傳,驗證檔案完整性
            upload_complete = True
            if device_id != 'WEB_UPLOAD':
                expected_size = int(request.form.get('file_size', 0))
                expected_hash = request.form.get('file_hash', '')

                if file_size != expected_size or file_hash != expected_hash:
                    return jsonify({'error': '檔案上傳不完整或已被修改'}), 400

            # 獲取或計算 duration
            duration = request.form.get('duration')
            if duration:
                duration = float(duration)
            else:
                # 網路上傳時自動計算音檔時長
                try:
                    audio_info = sf.info(BytesIO(file_data))
                    duration = audio_info.duration
                except Exception as e:
                    logger.warning(f"無法讀取音檔時長: {str(e)}")
                    duration = 0.0

            # 獲取音頻元數據
            metadata = {}
            try:
                audio_info = sf.info(BytesIO(file_data))
                metadata = {
                    'sample_rate': audio_info.samplerate,
                    'channels': audio_info.channels,
                    'format': audio_info.format
                }
            except Exception as e:
                logger.warning(f"無法讀取音頻元數據: {str(e)}")

            # 上傳到 GridFS
            try:
                file_id = mongodb_handler.gridfs_handler.upload_file(
                    file_data=file_data,
                    filename=filename,
                    content_type='audio/wav',
                    metadata={
                        'device_id': device_id,
                        'upload_time': datetime.now(Config.TAIPEI_TZ).isoformat(),
                        'file_hash': file_hash
                    }
                )
                logger.info(f"檔案上傳至 GridFS 成功: {filename} (ID: {file_id})")
            except Exception as e:
                logger.error(f"上傳至 GridFS 失敗: {str(e)}")
                return jsonify({'error': '檔案儲存失敗'}), 500

            # 建立錄音記錄
            new_recording = AudioRecording(
                filename=filename,
                duration=duration,
                device_id=device_id,
                file_size=file_size,
                file_hash=file_hash,
                file_id=file_id,  # GridFS 文件 ID
                upload_complete=upload_complete,
                metadata=metadata
            )

            # 插入 MongoDB
            recording_repo.insert(new_recording)

            # 發送 Socket.IO 事件
            socketio.emit('new_recording', new_recording.to_dict(), namespace='/')

            logger.info(f"成功上傳錄音: {filename} (來源: {device_id}, GridFS ID: {file_id})")
            return jsonify({'message': '檔案上傳成功', 'id': new_recording.analyze_uuid})
    except Exception as e:
        logger.error(f"上傳錄音時出錯: {str(e)}")
        return jsonify({'error': '檔案上傳失敗'}), 500


@app.route('/recordings', methods=['GET'])
def get_recordings():
    """
    獲取所有錄音的列表
    """
    try:
        recordings = recording_repo.find_all()
        return jsonify([r.to_dict() for r in recordings])
    except Exception as e:
        logger.error(f"獲取錄音列表時出錯: {str(e)}")
        return jsonify({'error': '獲取錄音列表失敗'}), 500


@app.route('/download/<id>', methods=['GET'])
def download_recording(id):
    """
    從 GridFS 下載指定ID的錄音檔案

    :param id: 錄音 UUID
    """
    try:
        recording = recording_repo.find_by_uuid(id)
        if not recording:
            return jsonify({'error': '找不到錄音記錄'}), 404

        if not recording.upload_complete:
            return jsonify({'error': '錄音尚未完成上傳,請稍後再試'}), 400

        if not recording.file_id:
            return jsonify({'error': 'GridFS 文件 ID 不存在'}), 404

        # 從 GridFS 下載文件
        file_data = mongodb_handler.gridfs_handler.download_file(recording.file_id)
        if not file_data:
            return jsonify({'error': 'GridFS 文件不存在或已損壞'}), 404

        # 返回文件
        return send_file(
            BytesIO(file_data),
            mimetype='audio/wav',
            as_attachment=True,
            download_name=recording.filename
        )
    except Exception as e:
        logger.error(f"下載錄音時出錯: {str(e)}")
        return jsonify({'error': '下載錄音失敗'}), 500


@app.route('/check_upload/<id>', methods=['GET'])
def check_upload(id):
    """
    檢查指定ID的錄音上傳狀態

    :param id: 錄音 UUID
    """
    try:
        recording = recording_repo.find_by_uuid(id)
        if not recording:
            return jsonify({'error': '找不到錄音記錄'}), 404

        return jsonify({'upload_complete': recording.upload_complete})
    except Exception as e:
        logger.error(f"檢查上傳狀態時出錯: {str(e)}")
        return jsonify({'error': '檢查上傳狀態失敗'}), 500


@app.route('/play/<id>', methods=['GET'])
def play_recording(id):
    """
    渲染播放指定ID錄音的頁面

    :param id: 錄音 UUID
    """
    try:
        recording = recording_repo.find_by_uuid(id)
        if not recording:
            return jsonify({'error': '找不到錄音記錄'}), 404

        # 轉換為字典格式以便模板使用
        recording_dict = recording.to_dict()

        # 獲取分析狀態和詳細資訊
        original_doc = recording_repo.collection.find_one({"AnalyzeUUID": recording.analyze_uuid})
        if original_doc:
            recording_dict['analysis_status'] = original_doc.get('analysis_status', 'pending')
            recording_dict['current_step'] = original_doc.get('current_step', 0)

            # 獲取分析摘要,並計算百分比
            analysis_summary = original_doc.get('analysis_summary', {})
            if analysis_summary and 'total_segments' in analysis_summary:
                total = analysis_summary.get('total_segments', 0)
                normal = analysis_summary.get('normal_count', 0)
                abnormal = analysis_summary.get('abnormal_count', 0)
                unknown = analysis_summary.get('unknown_count', 0)

                # 確保所有計數欄位都存在
                analysis_summary['normal_count'] = normal
                analysis_summary['abnormal_count'] = abnormal
                analysis_summary['unknown_count'] = unknown
                analysis_summary['total_segments'] = total

                # 計算百分比
                analysis_summary['normal_percentage'] = (normal / total * 100) if total > 0 else 0
                analysis_summary['abnormal_percentage'] = (abnormal / total * 100) if total > 0 else 0
                analysis_summary['unknown_percentage'] = (unknown / total * 100) if total > 0 else 0

            recording_dict['analysis_summary'] = analysis_summary
            recording_dict['analyze_features'] = original_doc.get('analyze_features', [])
        else:
            recording_dict['analysis_status'] = 'pending'
            recording_dict['current_step'] = 0
            recording_dict['analysis_summary'] = {}
            recording_dict['analyze_features'] = []

        return render_template('play.html', recording=recording_dict)
    except Exception as e:
        logger.error(f"播放錄音時出錯: {str(e)}")
        return jsonify({'error': '播放錄音失敗'}), 500


@app.route('/delete/<id>', methods=['POST'])
def delete_recording(id):
    """
    刪除指定ID的錄音(包含 GridFS 文件)

    :param id: 錄音 UUID
    """
    try:
        recording = recording_repo.find_by_uuid(id)
        if not recording:
            return jsonify({'error': '找不到錄音記錄'}), 404

        # 刪除記錄(會自動刪除 GridFS 文件)
        success = recording_repo.delete_by_uuid(id)

        if success:
            socketio.emit('recording_deleted', {'id': id})
            logger.info(f"成功刪除錄音: {recording.filename}")
            return jsonify({'message': '錄音已刪除', 'success': True})
        else:
            return jsonify({'error': '刪除失敗'}), 500
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
        interval = float(data.get('interval'))  # 間隔時間(分鐘)
        duration = int(data.get('duration'))  # 單次錄製時長(秒)
        count = data.get('count')  # 錄製次數(可選)

        if device_id not in recording_devices:
            return jsonify({'error': '設備未找到'}), 404

        if device_id in device_schedules:
            return jsonify({'error': '該設備已有排程,請先刪除原有排程'}), 400

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