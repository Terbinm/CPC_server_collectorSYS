"""
路由規則 API
提供路由規則的 CRUD 操作
"""
import logging
from flask import Blueprint, request, jsonify
from models.routing_rule import RoutingRule

logger = logging.getLogger(__name__)

routing_bp = Blueprint('routing_api', __name__)


@routing_bp.route('', methods=['GET'])
def get_all_rules():
    """獲取所有路由規則"""
    try:
        enabled_only = request.args.get('enabled_only', 'true').lower() == 'true'
        rules = RoutingRule.get_all(enabled_only=enabled_only)

        return jsonify({
            'success': True,
            'data': [rule.to_dict() for rule in rules],
            'count': len(rules)
        }), 200

    except Exception as e:
        logger.error(f"獲取路由規則列表失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routing_bp.route('/<rule_id>', methods=['GET'])
def get_rule(rule_id):
    """獲取單個路由規則"""
    try:
        rule = RoutingRule.get_by_id(rule_id)

        if not rule:
            return jsonify({
                'success': False,
                'error': '路由規則不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': rule.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"獲取路由規則失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routing_bp.route('', methods=['POST'])
def create_rule():
    """創建新路由規則"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '缺少請求數據'
            }), 400

        # 必填欄位驗證
        required_fields = ['rule_name', 'conditions', 'actions']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必填欄位: {field}'
                }), 400

        # 創建規則
        rule = RoutingRule.create(data)

        if not rule:
            return jsonify({
                'success': False,
                'error': '創建路由規則失敗'
            }), 500

        return jsonify({
            'success': True,
            'data': rule.to_dict(),
            'message': '路由規則已創建'
        }), 201

    except Exception as e:
        logger.error(f"創建路由規則失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routing_bp.route('/<rule_id>', methods=['PUT'])
def update_rule(rule_id):
    """更新路由規則"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '缺少請求數據'
            }), 400

        # 檢查規則是否存在
        rule = RoutingRule.get_by_id(rule_id)
        if not rule:
            return jsonify({
                'success': False,
                'error': '路由規則不存在'
            }), 404

        # 不允許修改的欄位
        protected_fields = ['rule_id', 'created_at']
        for field in protected_fields:
            if field in data:
                del data[field]

        # 更新規則
        success = RoutingRule.update(rule_id, data)

        if not success:
            return jsonify({
                'success': False,
                'error': '更新路由規則失敗'
            }), 500

        # 獲取更新後的規則
        rule = RoutingRule.get_by_id(rule_id)

        return jsonify({
            'success': True,
            'data': rule.to_dict(),
            'message': '路由規則已更新'
        }), 200

    except Exception as e:
        logger.error(f"更新路由規則失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routing_bp.route('/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """刪除路由規則"""
    try:
        # 檢查規則是否存在
        rule = RoutingRule.get_by_id(rule_id)
        if not rule:
            return jsonify({
                'success': False,
                'error': '路由規則不存在'
            }), 404

        # 刪除規則
        success = RoutingRule.delete(rule_id)

        if not success:
            return jsonify({
                'success': False,
                'error': '刪除路由規則失敗'
            }), 500

        return jsonify({
            'success': True,
            'message': '路由規則已刪除'
        }), 200

    except Exception as e:
        logger.error(f"刪除路由規則失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routing_bp.route('/test', methods=['POST'])
def test_rule():
    """測試路由規則匹配"""
    try:
        data = request.get_json()

        if not data or 'info_features' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 info_features'
            }), 400

        info_features = data['info_features']

        # 查找匹配的規則
        matching_rules = RoutingRule.find_matching_rules(info_features)

        return jsonify({
            'success': True,
            'data': {
                'matching_rules': [rule.to_dict() for rule in matching_rules],
                'match_count': len(matching_rules)
            }
        }), 200

    except Exception as e:
        logger.error(f"測試路由規則失敗: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
