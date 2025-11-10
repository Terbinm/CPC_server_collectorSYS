"""
权限装饰器
用于控制路由的访问权限
"""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)


def login_required(f):
    """
    要求用户登录的装饰器
    Flask-Login 已提供，此处为自定义版本
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    要求管理员权限的装饰器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))

        if not current_user.is_admin():
            logger.warning(f"用户 {current_user.username} 尝试访问管理员页面")
            flash('您没有权限访问此页面', 'danger')
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """
    要求特定角色的装饰器（工厂函数）

    Args:
        *roles: 允许的角色列表

    Usage:
        @role_required('admin', 'user')
        def some_view():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                logger.warning(
                    f"用户 {current_user.username} (角色: {current_user.role}) "
                    f"尝试访问需要角色 {roles} 的页面"
                )
                flash('您没有权限访问此页面', 'danger')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def active_required(f):
    """
    要求用户账户为激活状态的装饰器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))

        if not current_user.is_active:
            logger.warning(f"未激活用户 {current_user.username} 尝试访问")
            flash('您的账户已被停用，请联系管理员', 'danger')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function
