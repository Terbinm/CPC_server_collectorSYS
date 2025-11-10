"""
认证路由
处理用户登录、登出等功能
"""
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from flask_bcrypt import check_password_hash
from auth import auth_bp
from models.user import User
from forms.auth_forms import LoginForm
import logging

logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    登录页面和处理
    """
    # 如果已经登录，重定向到仪表板
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        remember = form.remember.data

        # 验证输入
        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('auth/login.html', form=form)

        # 查找用户
        user = User.find_by_username(username)

        if user is None:
            logger.warning(f"登录失败：用户不存在 - {username}")
            flash('用户名或密码错误', 'danger')
            return render_template('auth/login.html', form=form)

        # 检查账户是否激活
        if not user.is_active:
            logger.warning(f"登录失败：账户未激活 - {username}")
            flash('您的账户已被停用，请联系管理员', 'danger')
            return render_template('auth/login.html', form=form)

        # 验证密码
        if not check_password_hash(user.password_hash, password):
            logger.warning(f"登录失败：密码错误 - {username}")
            flash('用户名或密码错误', 'danger')
            return render_template('auth/login.html', form=form)

        # 登录成功
        login_user(user, remember=remember)
        user.update_last_login()

        logger.info(f"用户登录成功: {username}")
        flash(f'欢迎回来，{username}！', 'success')

        # 重定向到之前尝试访问的页面，或仪表板
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('views.dashboard'))

    if request.method == 'POST':
        flash('请检查输入内容', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
def logout():
    """
    登出处理
    """
    if current_user.is_authenticated:
        username = current_user.username
        logout_user()
        session.clear()
        logger.info(f"用户登出: {username}")
        flash('您已成功登出', 'info')
    else:
        flash('您还未登录', 'warning')

    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    """
    用户个人资料页面（未来扩展）
    """
    if not current_user.is_authenticated:
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login'))

    return render_template('auth/profile.html', user=current_user)
