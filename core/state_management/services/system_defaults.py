"""
系統預設資源管理
負責建立/同步程式 config 中定義的系統資源
"""
import logging
from typing import List, Dict, Any

from config import get_config
from models.analysis_config import AnalysisConfig

logger = logging.getLogger(__name__)


class SystemDefaultsService:
    """系統預設資源管理器"""

    @staticmethod
    def ensure_node_analysis_configs(node_id: str, node_info: Dict[str, Any]):
        """
        為節點自動建立內建分析設定

        Args:
            node_id: 節點 ID
            node_info: 節點資料（應包含 capabilities）
        """
        try:
            config = get_config()
            template = getattr(
                config,
                'SYSTEM_ANALYSIS_CONFIG_TEMPLATE',
                {}
            )

            capabilities: List[Any] = node_info.get('capabilities') or []
            if not capabilities:
                default_capability = template.get(
                    'default_capability',
                    'system_default'
                )
                capabilities = [default_capability]

            name_prefix = template.get('config_name_prefix', '系統自帶')
            description_tpl = template.get(
                'description_template',
                '系統自帶設定 - 節點 {node_id}（能力: {capability}）'
            )
            default_parameters = template.get('default_parameters', {})

            for capability in capabilities:
                capability_str = str(capability)
                capability_slug = capability_str.replace(':', '_').replace('.', '_')
                config_id = f"sys_{node_id}_{capability_slug}"

                parameters = {
                    **default_parameters,
                    'node_id': node_id,
                    'capability': capability_str
                }

                payload = {
                    'analysis_method_id': capability_str,
                    'config_id': config_id,
                    'config_name': f"{name_prefix} - {capability_str}@{node_id}",
                    'description': description_tpl.format(
                        node_id=node_id,
                        capability=capability_str
                    ),
                    'parameters': parameters,
                    'enabled': True,
                    'is_system': True
                }

                existing = AnalysisConfig.get_by_id(config_id)
                if existing:
                    # 僅同步描述/參數
                    AnalysisConfig.update(
                        config_id,
                        {
                            'config_name': payload['config_name'],
                            'description': payload['description'],
                            'parameters': payload['parameters'],
                            'enabled': True
                        },
                        allow_system=True
                    )
                else:
                    AnalysisConfig.create(payload)

            logger.info(
                "已為節點 %s 建立/同步 %d 個系統分析設定",
                node_id,
                len(capabilities)
            )

        except Exception as exc:
            logger.error(
                "建立節點系統分析設定失敗 (%s): %s",
                node_id,
                exc,
                exc_info=True
            )
