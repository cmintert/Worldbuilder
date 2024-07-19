from __future__ import annotations

from typing import Any, Dict


class Entity:
    def __init__(
        self, name: str, entity_type: str, description: str = None, **properties: Any
    ) -> None:
        self._properties = {
            "name": name,
            "entity_type": entity_type,
            "description": description,
        }
        self._properties.update(properties)
        self.relationships = []

    def __getattr__(self, name: str) -> Any:
        return self._properties.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ["_properties", "relationships"]:
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name: str) -> Any:
        return self._properties.get(name)

    def set_property(self, name: str, value: Any) -> None:
        self._properties[name] = value

    def delete_property(self, name: str) -> None:
        if name not in ["name", "entity_type", "description"]:
            self._properties.pop(name, None)

    def get_all_properties(self) -> Dict[str, Any]:
        return self._properties.copy()

    def add_relationship(
        self, rel_type: str, target: "Entity", **properties: Any
    ) -> "Relationship":
        relationship = Relationship(self, rel_type, target, **properties)
        self.relationships.append(relationship)
        return relationship

    def __repr__(self) -> str:
        return f"Entity(name={self.name}, type={self.entity_type})"


class Relationship:
    def __init__(
        self, source: Entity, rel_type: str, target: Entity, **properties: Any
    ) -> None:
        self._properties = {"source": source, "rel_type": rel_type, "target": target}
        self._properties.update(properties)

    def __getattr__(self, name: str) -> Any:
        return self._properties.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_properties":
            super().__setattr__(name, value)
        else:
            self._properties[name] = value

    def get_property(self, name: str) -> Any:
        return self._properties.get(name)

    def set_property(self, name: str, value: Any) -> None:
        self._properties[name] = value

    def delete_property(self, name: str) -> None:
        if name not in ["source", "rel_type", "target"]:
            self._properties.pop(name, None)

    def get_all_properties(self) -> Dict[str, Any]:
        return self._properties.copy()

    def __repr__(self) -> str:
        return f"{self.source.name} -> {self.rel_type} -> {self.target.name}"
