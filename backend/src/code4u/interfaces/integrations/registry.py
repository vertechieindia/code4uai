"""Integration registry for managing all integrations."""

from __future__ import annotations
from typing import Optional, Dict, List, Type, Any
import threading

from .base import (
    BaseIntegration,
    IntegrationType,
    IntegrationConfig,
    IntegrationEvent,
    EventType,
)


class IntegrationRegistry:
    """
    Central registry for all integrations.
    
    Manages:
    - Registration of integrations
    - Configuration per tenant
    - Event routing
    - Health monitoring
    """
    
    _instance: Optional[IntegrationRegistry] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> IntegrationRegistry:
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self) -> None:
        """Initialize registry."""
        self._integration_classes: Dict[str, Type[BaseIntegration]] = {}
        self._instances: Dict[str, Dict[str, BaseIntegration]] = {}  # tenant -> name -> instance
        self._configs: Dict[str, Dict[str, IntegrationConfig]] = {}  # tenant -> name -> config
    
    def register_class(
        self,
        name: str,
        integration_class: Type[BaseIntegration],
    ) -> None:
        """Register an integration class.
        
        Args:
            name: Integration name
            integration_class: Integration class
        """
        self._integration_classes[name] = integration_class
    
    def get_class(self, name: str) -> Optional[Type[BaseIntegration]]:
        """Get an integration class by name."""
        return self._integration_classes.get(name)
    
    def list_available(self) -> List[Dict[str, Any]]:
        """List all available integrations."""
        return [
            {
                "name": name,
                "type": cls.type.value if hasattr(cls, "type") else "unknown",
            }
            for name, cls in self._integration_classes.items()
        ]
    
    def configure(
        self,
        tenant_id: str,
        name: str,
        config: IntegrationConfig,
    ) -> None:
        """Configure an integration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            name: Integration name
            config: Configuration
        """
        if tenant_id not in self._configs:
            self._configs[tenant_id] = {}
        self._configs[tenant_id][name] = config
    
    def get_config(
        self,
        tenant_id: str,
        name: str,
    ) -> Optional[IntegrationConfig]:
        """Get configuration for an integration."""
        return self._configs.get(tenant_id, {}).get(name)
    
    async def get_instance(
        self,
        tenant_id: str,
        name: str,
    ) -> Optional[BaseIntegration]:
        """Get or create an integration instance.
        
        Args:
            tenant_id: Tenant identifier
            name: Integration name
            
        Returns:
            Integration instance or None
        """
        # Check existing
        if tenant_id in self._instances:
            if name in self._instances[tenant_id]:
                return self._instances[tenant_id][name]
        
        # Get class and config
        cls = self._integration_classes.get(name)
        if not cls:
            return None
        
        config = self._configs.get(tenant_id, {}).get(name, IntegrationConfig())
        
        # Create instance
        instance = cls(config)
        
        # Store
        if tenant_id not in self._instances:
            self._instances[tenant_id] = {}
        self._instances[tenant_id][name] = instance
        
        # Connect
        await instance.connect()
        
        return instance
    
    async def get_all_instances(
        self,
        tenant_id: str,
        integration_type: Optional[IntegrationType] = None,
    ) -> List[BaseIntegration]:
        """Get all integration instances for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            integration_type: Optional type filter
            
        Returns:
            List of integration instances
        """
        instances = []
        
        for name, config in self._configs.get(tenant_id, {}).items():
            if not config.enabled:
                continue
            
            instance = await self.get_instance(tenant_id, name)
            if instance:
                if integration_type is None or instance.type == integration_type:
                    instances.append(instance)
        
        return instances
    
    async def health_check_all(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Health check all integrations for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Health status for each integration
        """
        results = {}
        
        for name in self._instances.get(tenant_id, {}):
            instance = self._instances[tenant_id][name]
            try:
                results[name] = await instance.health_check()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        
        return results
    
    async def disconnect_all(self, tenant_id: str) -> None:
        """Disconnect all integrations for a tenant."""
        for instance in self._instances.get(tenant_id, {}).values():
            try:
                await instance.disconnect()
            except:
                pass
        
        if tenant_id in self._instances:
            del self._instances[tenant_id]


# Global registry
registry = IntegrationRegistry()


def register_integration(name: str):
    """Decorator to register an integration class.
    
    Args:
        name: Integration name
    """
    def decorator(cls: Type[BaseIntegration]):
        registry.register_class(name, cls)
        cls.name = name
        return cls
    return decorator

