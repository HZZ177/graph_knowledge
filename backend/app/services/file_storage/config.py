"""配置加载器"""

import yaml
from pathlib import Path
from typing import Dict, Any, List


class StorageConfig:
    """存储配置管理"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config['storage']
    
    @property
    def provider_name(self) -> str:
        """当前使用的提供商名称"""
        return self._config['provider']
    
    @property
    def provider_config(self) -> Dict[str, Any]:
        """当前提供商的配置"""
        provider_name = self.provider_name
        config = self._config.get(provider_name)
        
        if not config:
            raise ValueError(f"未找到提供商配置: {provider_name}")
        
        return config
    
    @property
    def max_file_size(self) -> int:
        """最大文件大小（字节）"""
        return self._config.get('max_file_size', 10 * 1024 * 1024)
    
    @property
    def allowed_extensions(self) -> List[str]:
        """允许的文件扩展名"""
        return self._config.get('allowed_extensions', [])
    
    @property
    def file_retention_days(self) -> int:
        """文件保留天数"""
        return self._config.get('file_retention_days', 7)
