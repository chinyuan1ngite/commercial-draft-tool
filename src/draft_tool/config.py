from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .security import atomic_write


@dataclass(frozen=True)
class TargetConfig:
    category_id: str | None = None
    category_name: str | None = None
    store_identity_text: str | None = None
    shipping_address: str | None = None
    freight_template_text: str | None = None
    delivery_promise: str | None = None
    package_weight_grams: int | None = None


@dataclass(frozen=True)
class QualityConfig:
    max_title_chars: int = 60
    min_main_images: int = 1
    require_detail_images: bool = True
    max_main_images: int = 4
    max_image_bytes: int = 5 * 1024 * 1024
    min_image_width: int = 800
    min_image_height: int = 800
    min_detail_width: int = 300
    min_detail_height: int = 100
    max_image_pixels: int = 40_000_000


@dataclass(frozen=True)
class AppConfig:
    version: int = 1
    target: TargetConfig = field(default_factory=TargetConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    profile_dir: Path = Path(".local/commercial-seller-browser")
    output_root: Path = Path("data/commercial-drafts")
    category_rules: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "AppConfig":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("配置文件必须是 JSON 对象")
        target = payload.get("target") or {}
        quality = payload.get("quality") or {}
        if not isinstance(target, dict) or not isinstance(quality, dict):
            raise ValueError("target 和 quality 必须是 JSON 对象")
        unknown_target = set(target) - set(TargetConfig.__dataclass_fields__)
        unknown_quality = set(quality) - set(QualityConfig.__dataclass_fields__)
        if unknown_target or unknown_quality:
            raise ValueError(f"配置包含未知字段: {sorted(unknown_target | unknown_quality)}")
        project_root = path.parent.parent if path.parent.name.lower() == "config" else path.parent
        profile_dir = Path(payload.get("profile_dir", ".local/commercial-seller-browser"))
        output_root = Path(payload.get("output_root", "data/commercial-drafts"))
        instance = cls(
            version=int(payload.get("version", 1)),
            target=TargetConfig(**{
                key: (target.get(key).strip() if isinstance(target.get(key), str) else target.get(key))
                for key in TargetConfig.__dataclass_fields__
            }),
            quality=QualityConfig(**{
                key: quality.get(key, getattr(QualityConfig(), key))
                for key in QualityConfig.__dataclass_fields__
            }),
            profile_dir=profile_dir if profile_dir.is_absolute() else project_root / profile_dir,
            output_root=output_root if output_root.is_absolute() else project_root / output_root,
            category_rules=dict(payload.get("category_rules") or {}),
        )
        numeric_quality = {
            key: getattr(instance.quality, key)
            for key in QualityConfig.__dataclass_fields__
            if key != "require_detail_images"
        }
        if not isinstance(instance.quality.require_detail_images, bool):
            raise ValueError("quality.require_detail_images 必须是布尔值")
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in numeric_quality.values()):
            raise ValueError("quality 数值配置必须为正整数")
        if instance.quality.min_main_images > instance.quality.max_main_images:
            raise ValueError("min_main_images 不能大于 max_main_images")
        if instance.target.package_weight_grams is not None:
            try:
                weight = int(instance.target.package_weight_grams)
            except (TypeError, ValueError) as exc:
                raise ValueError("package_weight_grams 必须是正整数") from exc
            if weight <= 0 or weight > 1_000_000:
                raise ValueError("package_weight_grams 超出有效范围")
            object.__setattr__(instance.target, "package_weight_grams", weight)
        return instance

    def effective_target(self, overrides: dict[str, Any]) -> TargetConfig:
        values = {
            key: overrides.get(key) if overrides.get(key) not in (None, "") else getattr(self.target, key)
            for key in TargetConfig.__dataclass_fields__
        }
        values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
        if values["package_weight_grams"] is not None:
            values["package_weight_grams"] = int(values["package_weight_grams"])
        return TargetConfig(**values)

    def rules_for(self, category_id: str | None) -> dict[str, Any]:
        by_category = self.category_rules.get("by_category")
        if isinstance(by_category, dict):
            return dict(by_category.get(str(category_id)) or {})
        return dict(self.category_rules)

    def write_runtime_record(self, output_dir: Path, target: TargetConfig) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "runtime-config.json"
        atomic_write(path, json.dumps({
            "config_version": self.version,
            "target": {
                "category_id": target.category_id,
                "category_name": target.category_name,
                "store_identity_text": target.store_identity_text,
                "shipping_address": target.shipping_address,
                "freight_template_text": target.freight_template_text,
                "delivery_promise": target.delivery_promise,
                "package_weight_grams": target.package_weight_grams,
            },
            "category_rules": self.rules_for(target.category_id),
        }, ensure_ascii=False, indent=2))
        return path
