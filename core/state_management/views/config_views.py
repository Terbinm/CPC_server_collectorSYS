"""
配置管理视图
处理分析配置的 CRUD 操作
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
    配置列表页面
    """
    try:
        # 获取查询参数
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'

        # 获取配置列表
        configs = AnalysisConfig.get_all(enabled_only=enabled_only)

        return render_template(
            'configs/list.html',
            configs=configs,
            enabled_only=enabled_only
        )

    except Exception as e:
        logger.error(f"加载配置列表失败: {str(e)}")
        flash('加载配置列表失败', 'danger')
        return render_template('configs/list.html', configs=[], enabled_only=False)


@views_bp.route('/configs/create', methods=['GET', 'POST'])
@admin_required
def config_create():
    """
    创建新配置
    """
    form = ConfigForm()

    if form.validate_on_submit():
        try:
            # 解析参数 JSON
            parameters = {}
            if form.parameters.data:
                try:
                    parameters = json.loads(form.parameters.data)
                except json.JSONDecodeError:
                    flash('参数 JSON 格式错误', 'danger')
                    return render_template('configs/edit.html', form=form, mode='create')

            # 创建配置
            config = AnalysisConfig.create(
                analysis_method_id=form.analysis_method_id.data,
                config_name=form.config_name.data,
                description=form.description.data,
                parameters=parameters,
                enabled=form.enabled.data
            )

            if config:
                logger.info(f"配置创建成功: {config.config_id}")
                flash('配置创建成功', 'success')
                return redirect(url_for('views.configs_list'))
            else:
                flash('配置创建失败', 'danger')

        except Exception as e:
            logger.error(f"创建配置失败: {str(e)}")
            flash(f'创建配置失败: {str(e)}', 'danger')

    return render_template('configs/edit.html', form=form, mode='create')


@views_bp.route('/configs/<config_id>/edit', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    """
    编辑配置
    """
    config = AnalysisConfig.get_by_id(config_id)
    if not config:
        flash('配置不存在', 'danger')
        return redirect(url_for('views.configs_list'))

    form = ConfigForm()

    if form.validate_on_submit():
        try:
            # 解析参数 JSON
            parameters = {}
            if form.parameters.data:
                try:
                    parameters = json.loads(form.parameters.data)
                except json.JSONDecodeError:
                    flash('参数 JSON 格式错误', 'danger')
                    return render_template(
                        'configs/edit.html',
                        form=form,
                        mode='edit',
                        config=config
                    )

            # 更新配置
            success = config.update(
                config_name=form.config_name.data,
                description=form.description.data,
                parameters=parameters,
                enabled=form.enabled.data
            )

            if success:
                logger.info(f"配置更新成功: {config_id}")
                flash('配置更新成功', 'success')
                return redirect(url_for('views.configs_list'))
            else:
                flash('配置更新失败', 'danger')

        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            flash(f'更新配置失败: {str(e)}', 'danger')

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
    查看配置详情
    """
    config = AnalysisConfig.get_by_id(config_id)
    if not config:
        flash('配置不存在', 'danger')
        return redirect(url_for('views.configs_list'))

    return render_template('configs/view.html', config=config)


@views_bp.route('/configs/<config_id>/delete', methods=['POST'])
@admin_required
def config_delete(config_id):
    """
    删除配置
    """
    try:
        success = AnalysisConfig.delete(config_id)

        if success:
            logger.info(f"配置删除成功: {config_id}")
            flash('配置删除成功', 'success')
        else:
            flash('配置删除失败', 'danger')

    except Exception as e:
        logger.error(f"删除配置失败: {str(e)}")
        flash(f'删除配置失败: {str(e)}', 'danger')

    return redirect(url_for('views.configs_list'))


@views_bp.route('/configs/<config_id>/toggle', methods=['POST'])
@admin_required
def config_toggle(config_id):
    """
    切换配置启用状态
    """
    try:
        config = AnalysisConfig.get_by_id(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        new_status = not config.enabled
        success = config.update(enabled=new_status)

        if success:
            logger.info(f"配置状态切换成功: {config_id} -> {new_status}")
            return jsonify({
                'success': True,
                'enabled': new_status,
                'message': f'配置已{"启用" if new_status else "禁用"}'
            })
        else:
            return jsonify({'success': False, 'message': '更新失败'}), 500

    except Exception as e:
        logger.error(f"切换配置状态失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
