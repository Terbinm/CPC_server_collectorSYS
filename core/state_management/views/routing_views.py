"""
路由规则管理视图
处理路由规则的 CRUD 操作
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from views import views_bp
from auth.decorators import admin_required
from forms.config_forms import RoutingRuleForm
from models.routing_rule import RoutingRule
import json
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/routing')
@login_required
def routing_list():
    """
    路由规则列表页面
    """
    try:
        # 获取查询参数
        enabled_only = request.args.get('enabled_only', 'true').lower() == 'true'

        # 获取规则列表（按优先级排序）
        rules = RoutingRule.get_all(enabled_only=enabled_only)

        return render_template(
            'routing/list.html',
            rules=rules,
            enabled_only=enabled_only
        )

    except Exception as e:
        logger.error(f"加载路由规则列表失败: {str(e)}")
        flash('加载路由规则列表失败', 'danger')
        return render_template('routing/list.html', rules=[], enabled_only=True)


@views_bp.route('/routing/create', methods=['GET', 'POST'])
@admin_required
def routing_create():
    """
    创建新路由规则
    """
    form = RoutingRuleForm()

    if form.validate_on_submit():
        try:
            # 解析 JSON 数据
            try:
                conditions = json.loads(form.conditions.data)
                actions = json.loads(form.actions.data)
                priority = int(form.priority.data)
            except (json.JSONDecodeError, ValueError) as e:
                flash(f'JSON 格式错误: {str(e)}', 'danger')
                return render_template('routing/edit.html', form=form, mode='create')

            # 创建规则
            rule = RoutingRule.create(
                rule_name=form.rule_name.data,
                description=form.description.data,
                priority=priority,
                conditions=conditions,
                actions=actions,
                enabled=form.enabled.data
            )

            if rule:
                logger.info(f"路由规则创建成功: {rule.rule_id}")
                flash('路由规则创建成功', 'success')
                return redirect(url_for('views.routing_list'))
            else:
                flash('路由规则创建失败', 'danger')

        except Exception as e:
            logger.error(f"创建路由规则失败: {str(e)}")
            flash(f'创建路由规则失败: {str(e)}', 'danger')

    return render_template('routing/edit.html', form=form, mode='create')


@views_bp.route('/routing/<rule_id>/edit', methods=['GET', 'POST'])
@admin_required
def routing_edit(rule_id):
    """
    编辑路由规则
    """
    rule = RoutingRule.get_by_id(rule_id)
    if not rule:
        flash('路由规则不存在', 'danger')
        return redirect(url_for('views.routing_list'))

    form = RoutingRuleForm()

    if form.validate_on_submit():
        try:
            # 解析 JSON 数据
            try:
                conditions = json.loads(form.conditions.data)
                actions = json.loads(form.actions.data)
                priority = int(form.priority.data)
            except (json.JSONDecodeError, ValueError) as e:
                flash(f'JSON 格式错误: {str(e)}', 'danger')
                return render_template(
                    'routing/edit.html',
                    form=form,
                    mode='edit',
                    rule=rule
                )

            # 更新规则
            success = rule.update(
                rule_name=form.rule_name.data,
                description=form.description.data,
                priority=priority,
                conditions=conditions,
                actions=actions,
                enabled=form.enabled.data
            )

            if success:
                logger.info(f"路由规则更新成功: {rule_id}")
                flash('路由规则更新成功', 'success')
                return redirect(url_for('views.routing_list'))
            else:
                flash('路由规则更新失败', 'danger')

        except Exception as e:
            logger.error(f"更新路由规则失败: {str(e)}")
            flash(f'更新路由规则失败: {str(e)}', 'danger')

    elif request.method == 'GET':
        # 填充表单数据
        form.rule_name.data = rule.rule_name
        form.description.data = rule.description
        form.priority.data = str(rule.priority)
        form.conditions.data = json.dumps(rule.conditions, indent=2, ensure_ascii=False)
        form.actions.data = json.dumps(rule.actions, indent=2, ensure_ascii=False)
        form.enabled.data = rule.enabled

    return render_template(
        'routing/edit.html',
        form=form,
        mode='edit',
        rule=rule
    )


@views_bp.route('/routing/<rule_id>/view')
@login_required
def routing_view(rule_id):
    """
    查看路由规则详情
    """
    rule = RoutingRule.get_by_id(rule_id)
    if not rule:
        flash('路由规则不存在', 'danger')
        return redirect(url_for('views.routing_list'))

    return render_template('routing/view.html', rule=rule)


@views_bp.route('/routing/<rule_id>/delete', methods=['POST'])
@admin_required
def routing_delete(rule_id):
    """
    删除路由规则
    """
    try:
        success = RoutingRule.delete(rule_id)

        if success:
            logger.info(f"路由规则删除成功: {rule_id}")
            flash('路由规则删除成功', 'success')
        else:
            flash('路由规则删除失败', 'danger')

    except Exception as e:
        logger.error(f"删除路由规则失败: {str(e)}")
        flash(f'删除路由规则失败: {str(e)}', 'danger')

    return redirect(url_for('views.routing_list'))


@views_bp.route('/routing/<rule_id>/toggle', methods=['POST'])
@admin_required
def routing_toggle(rule_id):
    """
    切换路由规则启用状态
    """
    try:
        rule = RoutingRule.get_by_id(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': '路由规则不存在'}), 404

        new_status = not rule.enabled
        success = rule.update(enabled=new_status)

        if success:
            logger.info(f"路由规则状态切换成功: {rule_id} -> {new_status}")
            return jsonify({
                'success': True,
                'enabled': new_status,
                'message': f'路由规则已{"启用" if new_status else "禁用"}'
            })
        else:
            return jsonify({'success': False, 'message': '更新失败'}), 500

    except Exception as e:
        logger.error(f"切换路由规则状态失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@views_bp.route('/routing/test', methods=['POST'])
@login_required
def routing_test():
    """
    测试路由规则匹配
    """
    try:
        data = request.get_json()
        if not data or 'info_features' not in data:
            return jsonify({
                'success': False,
                'message': '请提供 info_features 数据'
            }), 400

        info_features = data['info_features']

        # 测试匹配
        matched_rules = RoutingRule.test_match(info_features)

        return jsonify({
            'success': True,
            'matched_count': len(matched_rules),
            'matched_rules': [
                {
                    'rule_id': rule.rule_id,
                    'rule_name': rule.rule_name,
                    'priority': rule.priority,
                    'actions': rule.actions
                }
                for rule in matched_rules
            ]
        })

    except Exception as e:
        logger.error(f"测试路由规则失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
