"""
视图模块初始化
"""
from flask import Blueprint

# 创建视图蓝图
views_bp = Blueprint('views', __name__)

# 导入所有视图路由
from . import dashboard
from . import config_views
from . import routing_views
from . import instance_views
from . import node_views
from . import user_views
