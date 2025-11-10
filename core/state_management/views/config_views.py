"""
設定管理視圖
處理分析設定的 CRUD 操作
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from views import views_bp
from auth.decorators import admin_required
from forms.config_forms import ConfigForm, ModelUploadForm
from models.analysis_config import AnalysisConfig
import json
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/configs')
@login_required
def configs_list():
    """
    設定列表頁面
    """
    try:
        # 取得查詢參數
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'

        # 取得設定列表
        configs = AnalysisConfig.get_all(enabled_only=enabled_only)

        return render_template(
            'configs/list.html',
            configs=configs,
            enabled_only=enabled_only
        )

    except Exception as e:
        logger.error(f"載入設定列表失敗: {str(e)}")
        flash('載入設定列表失敗', 'danger')
        return render_template('configs/list.html', configs=[], enabled_only=False)


@views_bp.route('/configs/create', methods=['GET', 'POST'])
@admin_required
def config_create():
    """
    建立新設定
    """
    form = ConfigForm()

    if form.validate_on_submit():
        try:
            # 解析參數 JSON
            parameters = {}
            if form.parameters.data:
                try:
                    parameters = json.loads(form.parameters.data)
                except json.JSONDecodeError:
                    flash('參數 JSON 格式錯誤', 'danger')
                    return render_template('configs/edit.html', form=form, mode='create')

            # 建立設定
            config = AnalysisConfig.create(
                analysis_method_id=form.analysis_method_id.data,
                config_name=form.config_name.data,
                description=form.description.data,
                parameters=parameters,
                enabled=form.enabled.data
            )

            if config:
                logger.info(f"設定建立成功: {config.config_id}")
                flash('設定建立成功', 'success')
                return redirect(url_for('views.configs_list'))
            else:
                flash('設定建立失敗', 'danger')

        except Exception as e:
            logger.error(f"建立設定失敗: {str(e)}")
            flash(f'建立設定失敗: {str(e)}', 'danger')

    return render_template('configs/edit.html', form=form, mode='create')


@views_bp.route('/configs/<config_id>/edit', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    """
    編輯設定
    """
    config = AnalysisConfig.get_by_id(config_id)
    if not config:
        flash('設定不存在', 'danger')
        return redirect(url_for('views.configs_list'))

    form = ConfigForm()

    if form.validate_on_submit():
        try:
            # 解析參數 JSON
            parameters = {}
            if form.parameters.data:
                try:
                    parameters = json.loads(form.parameters.data)
                except json.JSONDecodeError:
                    flash('參數 JSON 格式錯誤', 'danger')
                    return render_template(
                        'configs/edit.html',
                        form=form,
                        mode='edit',
                        config=config
                    )

            # 更新設定
            success = config.update(
                config_name=form.config_name.data,
                description=form.description.data,
                parameters=parameters,
                enabled=form.enabled.data
            )

            if success:
                logger.info(f"設定更新成功: {config_id}")
                flash('設定更新成功', 'success')
                return redirect(url_for('views.configs_list'))
            else:
                flash('設定更新失敗', 'danger')

        except Exception as e:
            logger.error(f"更新設定失敗: {str(e)}")
            flash(f'更新設定失敗: {str(e)}', 'danger')

    elif request.method == 'GET':
        # 填充表单数据
        form.analysis_method_id.data = config.analysis_method_id
        form.config_name.data = config.config_name
        form.description.data = config.description
        form.parameters.data = json.dumps(config.parameters, indent=2, ensure_ascii=False)
        form.enabled.data = config.enabled

    return render_template(
        'configs/edit.html',
        form=form,
        mode='edit',
        config=config
    )


@views_bp.route('/configs/<config_id>/view')
@login_required
def config_view(config_id):
    """
    查看設定詳情
    """
    config = AnalysisConfig.get_by_id(config_id)
    if not config:
        flash('設定不存在', 'danger')
        return redirect(url_for('views.configs_list'))

    return render_template('configs/view.html', config=config)


@views_bp.route('/configs/<config_id>/delete', methods=['POST'])
@admin_required
def config_delete(config_id):
    """
    刪除設定
    """
    try:
        success = AnalysisConfig.delete(config_id)

        if success:
            logger.info(f"設定刪除成功: {config_id}")
            flash('設定刪除成功', 'success')
        else:
            flash('設定刪除失敗', 'danger')

    except Exception as e:
        logger.error(f"刪除設定失敗: {str(e)}")
        flash(f'刪除設定失敗: {str(e)}', 'danger')

    return redirect(url_for('views.configs_list'))


@views_bp.route('/configs/<config_id>/toggle', methods=['POST'])
@admin_required
def config_toggle(config_id):
    """
    切換設定啟用狀態
    """
    try:
        config = AnalysisConfig.get_by_id(config_id)
        if not config:
            return jsonify({'success': False, 'message': '設定不存在'}), 404

        new_status = not config.enabled
        success = config.update(enabled=new_status)

        if success:
            logger.info(f"設定狀態切換成功: {config_id} -> {new_status}")
            return jsonify({
                'success': True,
                'enabled': new_status,
                'message': f'設定已{"啟用" if new_status else "停用"}'
            })
        else:
            return jsonify({'success': False, 'message': '更新失敗'}), 500

    except Exception as e:
        logger.error(f"切換設定狀態失敗: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
