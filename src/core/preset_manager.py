"""
预设管理 —— PresetManager

【What】
管理系统内置预设和用户自定义预设的 CRUD。

【覆盖需求】
D1(系统内置预设)  D2(自定义预设)  D3(预设选择)  D4(预设管理菜单接口)

【Why】
- 内置预设（user_id IS NULL, is_builtin=True）所有用户共享，不可删除/编辑
- 自定义预设（user_id != None）归属到具体用户，支持完整 CRUD
- D3 预设选择在会话创建时由 TUI 调用 get_preset 获取预设内容

【Where】
- TUI 菜单调用 list_builtin_presets / list_user_presets 展示预设列表
- TUI 调用 create_preset / update_preset / delete_preset 管理用户预设
- SessionManager 新建会话时可选关联 preset_id
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from src.models.schemas import Preset, PresetCreate
from src.storage.base import StorageBackend

_LOGGER = logging.getLogger(__name__)
_PRESETS_YAML = Path(__file__).resolve().parent.parent.parent / "config" / "presets.yaml"


class PresetManager:
    """预设管理

    权限校验顺序（update / delete 共用）:
        1. 存在性 → 不存在则抛 ValueError
        2. 内置标记 → is_builtin 则抛 ValueError
        3. 归属校验 → user_id 不匹配则抛 ValueError
    """

    def __init__(self, backend: StorageBackend, user_id: int):
        self._backend = backend
        self._user_id = user_id

    # ==================================================================
    # D1 — 系统内置预设（只读）
    # ==================================================================

    async def list_builtin_presets(self) -> list[Preset]:
        """获取所有系统内置预设（全用户共享，只读）"""
        return await self._backend.get_builtin_presets()

    @staticmethod
    async def sync_builtin_presets(backend: StorageBackend) -> None:
        """将 config/presets.yaml 中的内置预设同步至数据库

        同步规则（以 slug 为匹配键）：
        - YAML 有、DB 无              → INSERT
        - YAML 有、DB 有、内容不同    → UPDATE
        - YAML 有、DB 有、内容相同    → 跳过
        - YAML 无、DB 有              → DELETE（删除前清空 sessions 引用）

        YAML 不存在或解析失败时仅打日志，不阻止程序启动。
        """
        if not _PRESETS_YAML.exists():
            _LOGGER.warning("presets.yaml not found, skipping builtin preset sync")
            return

        with open(_PRESETS_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        yaml_presets: list[dict] = data.get("presets", [])
        if not yaml_presets:
            _LOGGER.info("No presets defined in presets.yaml")
            return

        db_builtins = await backend.get_builtin_presets()
        db_by_slug: dict[str, Preset] = {p.slug: p for p in db_builtins if p.slug}

        yaml_slugs: set[str] = set()

        for item in yaml_presets:
            slug = item.get("slug")
            if not slug:
                _LOGGER.warning("Skipping preset with missing slug: %s", item.get("name"))
                continue
            yaml_slugs.add(slug)

            existing = db_by_slug.get(slug)
            name = item["name"]
            description = item.get("description")
            system_prompt = item["system_prompt"]

            if existing is None:
                await backend.create_preset(
                    PresetCreate(
                        user_id=None,
                        name=name,
                        description=description,
                        system_prompt=system_prompt,
                        slug=slug,
                        is_builtin=True,
                    ),
                )
                _LOGGER.info("Builtin preset created", extra={"slug": slug, "name": name})
            elif existing.system_prompt != system_prompt:
                existing.name = name
                existing.description = description
                existing.system_prompt = system_prompt
                await backend.update_preset(existing)
                _LOGGER.info("Builtin preset updated", extra={"slug": slug, "name": name})
            else:
                _LOGGER.debug("Builtin preset unchanged", extra={"slug": slug})

        # 删除 YAML 中已移除的旧内置预设
        for db_p in db_builtins:
            if db_p.slug and db_p.slug not in yaml_slugs:
                await backend.delete_preset(db_p.id)
                _LOGGER.info("Builtin preset removed (no longer in yaml)", extra={"slug": db_p.slug, "name": db_p.name})

    # ==================================================================
    # D2/D4 — 用户自定义预设列表
    # ==================================================================

    async def list_user_presets(self) -> list[Preset]:
        """获取当前用户的所有自定义预设"""
        return await self._backend.get_user_presets(self._user_id)

    # ==================================================================
    # D3 — 按 ID 获取预设（不分归属，会话创建时使用）
    # ==================================================================

    async def get_preset(self, preset_id: int) -> Optional[Preset]:
        """按 ID 获取预设

        不校验归属，任何用户都可查询任意预设（内置或他人的均可），
        用于会话创建时根据 preset_id 加载预设内容。
        """
        return await self._backend.get_preset(preset_id)

    # ==================================================================
    # D2 — 创建自定义预设
    # ==================================================================

    async def create_preset(
        self,
        name: str,
        system_prompt: str,
        description: Optional[str] = None,
    ) -> Preset:
        """创建自定义预设

        Args:
            name: 预设名称
            system_prompt: 系统提示词
            description: 预设描述（可选）
        """
        preset = await self._backend.create_preset(
            PresetCreate(
                user_id=self._user_id,
                name=name,
                description=description,
                system_prompt=system_prompt,
            ),
        )
        _LOGGER.info("Preset created", extra={"preset_id": preset.id, "name": name, "user_id": self._user_id})
        return preset

    # ==================================================================
    # D2 — 更新预设（三步校验）
    # ==================================================================

    async def update_preset(
        self,
        preset_id: int,
        name: str,
        description: Optional[str],
        system_prompt: str,
    ) -> Preset:
        """更新预设

        Args:
            preset_id: 目标预设 ID
            name: 新名称
            description: 新描述（None 可清空）
            system_prompt: 新系统提示词

        Raises:
            ValueError: 预设不存在 / 内置预设 / 无权操作
        """
        preset = await self._assert_can_modify(preset_id)

        preset.name = name
        preset.description = description
        preset.system_prompt = system_prompt
        return await self._backend.update_preset(preset)

    # ==================================================================
    # D2 — 删除预设（三步校验）
    # ==================================================================

    async def delete_preset(self, preset_id: int) -> None:
        """删除预设

        Raises:
            ValueError: 预设不存在 / 内置预设 / 无权操作
        """
        preset = await self._assert_can_modify(preset_id)
        await self._backend.delete_preset(preset_id)
        _LOGGER.info("Preset deleted", extra={"preset_id": preset_id, "name": preset.name, "user_id": self._user_id})

    # ==================================================================
    # 内部辅助
    # ==================================================================

    async def _assert_can_modify(self, preset_id: int) -> Preset:
        """三步校验：存在 → 非内置 → 归属当前用户，通过后返回 Preset"""
        preset = await self._backend.get_preset(preset_id)
        if preset is None:
            raise ValueError(f"预设 {preset_id} 不存在")
        if preset.is_builtin:
            raise ValueError("内置预设不可编辑或删除")
        if preset.user_id != self._user_id:
            raise ValueError("无权操作其他用户的预设")
        return preset
