"""
认证模块初始化
"""
from flask import Blueprint

# 创建认证蓝图
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 导入路由
from . import routes
