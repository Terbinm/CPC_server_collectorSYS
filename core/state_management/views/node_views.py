"""
节点监控视图
显示和管理分析节点的状态
"""
from flask import render_template, redirect, url_for, flash, jsonify
from flask_login import login_required
from views import views_bp
from auth.decorators import admin_required
from models.node_status import NodeStatus
import logging

logger = logging.getLogger(__name__)


@views_bp.route('/nodes')
@login_required
def nodes_list():
    """
    节点列表页面
    显示所有注册节点的状态
    """
    try:
        # 获取所有节点
        all_nodes = NodeStatus.get_all()

        # 分类节点
        online_nodes = [node for node in all_nodes if node.is_online()]
        offline_nodes = [node for node in all_nodes if not node.is_online()]

        # 统计信息
        stats = {
            'total': len(all_nodes),
            'online': len(online_nodes),
            'offline': len(offline_nodes)
        }

        return render_template(
            'nodes/list.html',
            online_nodes=online_nodes,
            offline_nodes=offline_nodes,
            stats=stats
        )

    except Exception as e:
        logger.error(f"加载节点列表失败: {str(e)}")
        flash('加载节点列表失败', 'danger')
        return render_template(
            'nodes/list.html',
            online_nodes=[],
            offline_nodes=[],
            stats={'total': 0, 'online': 0, 'offline': 0}
        )


@views_bp.route('/nodes/<node_id>')
@login_required
def node_detail(node_id):
    """
    节点详情页面
    """
    try:
        node = NodeStatus.get_by_id(node_id)
        if not node:
            flash('节点不存在', 'danger')
            return redirect(url_for('views.nodes_list'))

        return render_template('nodes/detail.html', node=node)

    except Exception as e:
        logger.error(f"加载节点详情失败: {str(e)}")
        flash('加载节点详情失败', 'danger')
        return redirect(url_for('views.nodes_list'))


@views_bp.route('/nodes/<node_id>/delete', methods=['POST'])
@admin_required
def node_delete(node_id):
    """
    删除（注销）节点
    """
    try:
        success = NodeStatus.delete(node_id)

        if success:
            logger.info(f"节点删除成功: {node_id}")
            flash('节点删除成功', 'success')
        else:
            flash('节点删除失败', 'danger')

    except Exception as e:
        logger.error(f"删除节点失败: {str(e)}")
        flash(f'删除节点失败: {str(e)}', 'danger')

    return redirect(url_for('views.nodes_list'))


@views_bp.route('/api/nodes/stats')
@login_required
def nodes_stats_api():
    """
    节点统计信息 API（用于前端轮询）
    """
    try:
        all_nodes = NodeStatus.get_all()
        online_count = sum(1 for node in all_nodes if node.is_online())

        return jsonify({
            'success': True,
            'stats': {
                'total': len(all_nodes),
                'online': online_count,
                'offline': len(all_nodes) - online_count
            }
        })

    except Exception as e:
        logger.error(f"获取节点统计信息失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@views_bp.route('/api/nodes/list')
@login_required
def nodes_list_api():
    """
    节点列表 API（用于前端轮询）
    """
    try:
        all_nodes = NodeStatus.get_all()

        nodes_data = [
            {
                'node_id': node.node_id,
                'capabilities': node.capabilities,
                'version': node.version,
                'max_concurrent_tasks': node.max_concurrent_tasks,
                'current_tasks': node.current_tasks,
                'last_heartbeat': node.last_heartbeat.isoformat() if node.last_heartbeat else None,
                'is_online': node.is_online(),
                'tags': node.tags
            }
            for node in all_nodes
        ]

        return jsonify({
            'success': True,
            'nodes': nodes_data
        })

    except Exception as e:
        logger.error(f"获取节点列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
