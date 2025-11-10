"""
用户管理视图（仅管理员）
处理用户的 CRUD 操作
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user
from flask_bcrypt import generate_password_hash, check_password_hash
from views import views_bp
from auth.decorators import admin_required
from forms.auth_forms import UserCreateForm, UserEditForm, ChangePasswordForm
from models.user import User
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/users')
@admin_required
def users_list():
    """
    用户列表页面（仅管理员）
    """
    try:
        # 获取查询参数
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

        # 获取用户列表
        users = User.get_all(include_inactive=include_inactive)

        return render_template(
            'users/list.html',
            users=users,
            include_inactive=include_inactive
        )

    except Exception as e:
        logger.error(f"加载用户列表失败: {str(e)}")
        flash('加载用户列表失败', 'danger')
        return render_template('users/list.html', users=[], include_inactive=False)


@views_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def user_create():
    """
    创建新用户（仅管理员）
    """
    form = UserCreateForm()

    if form.validate_on_submit():
        try:
            # 生成密码哈希
            password_hash = generate_password_hash(form.password.data).decode('utf-8')

            # 创建用户
            user = User.create(
                username=form.username.data,
                email=form.email.data,
                password_hash=password_hash,
                role=form.role.data
            )

            if user:
                logger.info(f"用户创建成功: {user.username} (by {current_user.username})")
                flash(f'用户 {user.username} 创建成功', 'success')
                return redirect(url_for('views.users_list'))
            else:
                flash('用户创建失败', 'danger')

        except Exception as e:
            logger.error(f"创建用户失败: {str(e)}")
            flash(f'创建用户失败: {str(e)}', 'danger')

    return render_template('users/create.html', form=form)


@views_bp.route('/users/<username>/edit', methods=['GET', 'POST'])
@admin_required
def user_edit(username):
    """
    编辑用户（仅管理员）
    """
    user = User.find_by_username(username)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('views.users_list'))

    # 不允许编辑自己的账户
    if user.username == current_user.username:
        flash('不能编辑自己的账户，请使用个人资料页面', 'warning')
        return redirect(url_for('views.users_list'))

    form = UserEditForm()

    if form.validate_on_submit():
        try:
            # 更新用户信息
            success = user.update(
                email=form.email.data,
                role=form.role.data,
                is_active=form.is_active.data
            )

            if success:
                logger.info(f"用户信息更新成功: {username} (by {current_user.username})")
                flash('用户信息更新成功', 'success')
                return redirect(url_for('views.users_list'))
            else:
                flash('用户信息更新失败', 'danger')

        except Exception as e:
            logger.error(f"更新用户信息失败: {str(e)}")
            flash(f'更新用户信息失败: {str(e)}', 'danger')

    elif request.method == 'GET':
        # 填充表单数据
        form.email.data = user.email
        form.role.data = user.role
        form.is_active.data = user.is_active

    return render_template('users/edit.html', form=form, user=user)


@views_bp.route('/users/<username>/view')
@admin_required
def user_view(username):
    """
    查看用户详情（仅管理员）
    """
    user = User.find_by_username(username)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('views.users_list'))

    return render_template('users/view.html', user=user)


@views_bp.route('/users/<username>/delete', methods=['POST'])
@admin_required
def user_delete(username):
    """
    删除用户（软删除，仅管理员）
    """
    try:
        # 不允许删除自己
        if username == current_user.username:
            flash('不能删除自己的账户', 'danger')
            return redirect(url_for('views.users_list'))

        user = User.find_by_username(username)
        if not user:
            flash('用户不存在', 'danger')
            return redirect(url_for('views.users_list'))

        success = user.delete()

        if success:
            logger.info(f"用户删除成功: {username} (by {current_user.username})")
            flash(f'用户 {username} 已被停用', 'success')
        else:
            flash('用户删除失败', 'danger')

    except Exception as e:
        logger.error(f"删除用户失败: {str(e)}")
        flash(f'删除用户失败: {str(e)}', 'danger')

    return redirect(url_for('views.users_list'))


@views_bp.route('/users/<username>/reset-password', methods=['POST'])
@admin_required
def user_reset_password(username):
    """
    重置用户密码（仅管理员）
    """
    try:
        user = User.find_by_username(username)
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404

        # 生成临时密码（可以改为发送邮件）
        import secrets
        temp_password = secrets.token_urlsafe(12)
        password_hash = generate_password_hash(temp_password).decode('utf-8')

        success = user.update(password_hash=password_hash)

        if success:
            logger.info(f"密码重置成功: {username} (by {current_user.username})")
            return jsonify({
                'success': True,
                'message': f'密码已重置',
                'temp_password': temp_password
            })
        else:
            return jsonify({'success': False, 'message': '重置失败'}), 500

    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@views_bp.route('/profile/change-password', methods=['GET', 'POST'])
def change_password():
    """
    修改自己的密码
    """
    if not current_user.is_authenticated:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    form = ChangePasswordForm()

    if form.validate_on_submit():
        try:
            # 验证当前密码
            if not check_password_hash(current_user.password_hash, form.current_password.data):
                flash('当前密码错误', 'danger')
                return render_template('users/change_password.html', form=form)

            # 更新密码
            new_password_hash = generate_password_hash(form.new_password.data).decode('utf-8')
            success = current_user.update(password_hash=new_password_hash)

            if success:
                logger.info(f"密码修改成功: {current_user.username}")
                flash('密码修改成功', 'success')
                return redirect(url_for('views.dashboard'))
            else:
                flash('密码修改失败', 'danger')

        except Exception as e:
            logger.error(f"修改密码失败: {str(e)}")
            flash(f'修改密码失败: {str(e)}', 'danger')

    return render_template('users/change_password.html', form=form)
