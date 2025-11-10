"""
MongoDB 实例管理视图
处理 MongoDB 实例的 CRUD 操作
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from views import views_bp
from auth.decorators import admin_required
from forms.config_forms import MongoDBInstanceForm
from models.mongodb_instance import MongoDBInstance
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/instances')
@login_required
def instances_list():
    """
    MongoDB 实例列表页面
    """
    try:
        # 获取查询参数
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'

        # 获取实例列表（不包含密码）
        instances = MongoDBInstance.get_all(
            enabled_only=enabled_only,
            include_password=False
        )

        return render_template(
            'instances/list.html',
            instances=instances,
            enabled_only=enabled_only
        )

    except Exception as e:
        logger.error(f"加载 MongoDB 实例列表失败: {str(e)}")
        flash('加载实例列表失败', 'danger')
        return render_template('instances/list.html', instances=[], enabled_only=False)


@views_bp.route('/instances/create', methods=['GET', 'POST'])
@admin_required
def instance_create():
    """
    创建新 MongoDB 实例
    """
    form = MongoDBInstanceForm()

    if form.validate_on_submit():
        try:
            # 创建实例
            instance = MongoDBInstance.create(
                instance_name=form.instance_name.data,
                description=form.description.data,
                host=form.host.data,
                port=int(form.port.data),
                username=form.username.data,
                password=form.password.data,
                database=form.database.data,
                collection=form.collection.data or 'recordings',
                auth_source=form.auth_source.data or 'admin',
                enabled=form.enabled.data
            )

            if instance:
                logger.info(f"MongoDB 实例创建成功: {instance.instance_id}")
                flash('MongoDB 实例创建成功', 'success')
                return redirect(url_for('views.instances_list'))
            else:
                flash('MongoDB 实例创建失败', 'danger')

        except Exception as e:
            logger.error(f"创建 MongoDB 实例失败: {str(e)}")
            flash(f'创建实例失败: {str(e)}', 'danger')

    return render_template('instances/edit.html', form=form, mode='create')


@views_bp.route('/instances/<instance_id>/edit', methods=['GET', 'POST'])
@admin_required
def instance_edit(instance_id):
    """
    编辑 MongoDB 实例
    """
    instance = MongoDBInstance.get_by_id(instance_id, include_password=True)
    if not instance:
        flash('MongoDB 实例不存在', 'danger')
        return redirect(url_for('views.instances_list'))

    form = MongoDBInstanceForm()

    if form.validate_on_submit():
        try:
            # 更新实例
            success = instance.update(
                instance_name=form.instance_name.data,
                description=form.description.data,
                host=form.host.data,
                port=int(form.port.data),
                username=form.username.data,
                password=form.password.data,
                database=form.database.data,
                collection=form.collection.data or 'recordings',
                auth_source=form.auth_source.data or 'admin',
                enabled=form.enabled.data
            )

            if success:
                logger.info(f"MongoDB 实例更新成功: {instance_id}")
                flash('MongoDB 实例更新成功', 'success')
                return redirect(url_for('views.instances_list'))
            else:
                flash('MongoDB 实例更新失败', 'danger')

        except Exception as e:
            logger.error(f"更新 MongoDB 实例失败: {str(e)}")
            flash(f'更新实例失败: {str(e)}', 'danger')

    elif request.method == 'GET':
        # 填充表单数据
        form.instance_name.data = instance.instance_name
        form.description.data = instance.description
        form.host.data = instance.host
        form.port.data = str(instance.port)
        form.username.data = instance.username
        form.password.data = instance.password
        form.database.data = instance.database
        form.collection.data = instance.collection
        form.auth_source.data = instance.auth_source
        form.enabled.data = instance.enabled

    return render_template(
        'instances/edit.html',
        form=form,
        mode='edit',
        instance=instance
    )


@views_bp.route('/instances/<instance_id>/view')
@login_required
def instance_view(instance_id):
    """
    查看 MongoDB 实例详情
    """
    instance = MongoDBInstance.get_by_id(instance_id, include_password=False)
    if not instance:
        flash('MongoDB 实例不存在', 'danger')
        return redirect(url_for('views.instances_list'))

    return render_template('instances/view.html', instance=instance)


@views_bp.route('/instances/<instance_id>/delete', methods=['POST'])
@admin_required
def instance_delete(instance_id):
    """
    删除 MongoDB 实例
    """
    try:
        success = MongoDBInstance.delete(instance_id)

        if success:
            logger.info(f"MongoDB 实例删除成功: {instance_id}")
            flash('MongoDB 实例删除成功', 'success')
        else:
            flash('MongoDB 实例删除失败', 'danger')

    except Exception as e:
        logger.error(f"删除 MongoDB 实例失败: {str(e)}")
        flash(f'删除实例失败: {str(e)}', 'danger')

    return redirect(url_for('views.instances_list'))


@views_bp.route('/instances/<instance_id>/toggle', methods=['POST'])
@admin_required
def instance_toggle(instance_id):
    """
    切换 MongoDB 实例启用状态
    """
    try:
        instance = MongoDBInstance.get_by_id(instance_id)
        if not instance:
            return jsonify({'success': False, 'message': '实例不存在'}), 404

        new_status = not instance.enabled
        success = instance.update(enabled=new_status)

        if success:
            logger.info(f"MongoDB 实例状态切换成功: {instance_id} -> {new_status}")
            return jsonify({
                'success': True,
                'enabled': new_status,
                'message': f'实例已{"启用" if new_status else "禁用"}'
            })
        else:
            return jsonify({'success': False, 'message': '更新失败'}), 500

    except Exception as e:
        logger.error(f"切换 MongoDB 实例状态失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@views_bp.route('/instances/<instance_id>/test', methods=['POST'])
@admin_required
def instance_test(instance_id):
    """
    测试 MongoDB 实例连接
    """
    try:
        instance = MongoDBInstance.get_by_id(instance_id, include_password=True)
        if not instance:
            return jsonify({'success': False, 'message': '实例不存在'}), 404

        # 测试连接
        success, message = instance.test_connection()

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        logger.error(f"测试 MongoDB 连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
