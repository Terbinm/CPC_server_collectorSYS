"""
仪表板视图
显示系统概览和统计信息
"""
from flask import render_template
from flask_login import login_required
from views import views_bp
from models.analysis_config import AnalysisConfig
from models.routing_rule import RoutingRule
from models.mongodb_instance import MongoDBInstance
from models.node_status import NodeStatus
from models.user import User
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/')
@views_bp.route('/dashboard')
@login_required
def dashboard():
    """
    仪表板主页
    显示系统整体状态和统计信息
    """
    try:
        # 获取统计数据
        stats = {
            'configs': {
                'total': AnalysisConfig.count_all(),
                'enabled': AnalysisConfig.count_enabled()
            },
            'routing_rules': {
                'total': RoutingRule.count_all(),
                'enabled': RoutingRule.count_enabled()
            },
            'mongodb_instances': {
                'total': MongoDBInstance.count_all(),
                'enabled': MongoDBInstance.count_enabled()
            },
            'nodes': {
                'total': NodeStatus.count_all(),
                'online': NodeStatus.count_online()
            },
            'users': {
                'total': User.get_all(include_inactive=True).__len__(),
                'active': User.get_all(include_inactive=False).__len__()
            }
        }

        # 获取最近更新的配置（前5个）
        recent_configs = AnalysisConfig.get_all(limit=5)

        # 获取在线节点列表
        online_nodes = NodeStatus.get_online_nodes()

        return render_template(
            'dashboard.html',
            stats=stats,
            recent_configs=recent_configs,
            online_nodes=online_nodes
        )

    except Exception as e:
        logger.error(f"加载仪表板数据失败: {str(e)}")
        return render_template(
            'dashboard.html',
            stats={},
            recent_configs=[],
            online_nodes=[],
            error="加载数据失败"
        )
