"""
预设管理单元测试 —— test_preset_manager

【覆盖需求】
D1(系统内置预设)  D2(自定义预设)  D3(预设选择)  D4(预设管理菜单接口)
"""

import pytest

from pathlib import Path

import yaml

from src.core.preset_manager import PresetManager
from src.models.schemas import PresetCreate, User, UserCreate, SessionCreate
from src.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def mgr(tmp_sqlite_backend: SQLiteBackend, test_user: User) -> PresetManager:
    """返回一个绑定测试用户的 PresetManager 实例"""
    return PresetManager(backend=tmp_sqlite_backend, user_id=test_user.id)


@pytest.fixture
async def builtin_preset(tmp_sqlite_backend: SQLiteBackend) -> None:
    """创建一个系统内置预设"""
    await tmp_sqlite_backend.create_preset(
        PresetCreate(
            user_id=None,
            name="通用助手",
            description="通用对话助手",
            system_prompt="你是一个有用的助手",
            is_builtin=True,
        ),
    )


@pytest.fixture
async def user_preset(
    mgr: PresetManager,
) -> None:
    """通过 Manager 创建一个用户预设"""
    await mgr.create_preset(
        name="代码专家",
        system_prompt="你是一个代码专家",
    )


@pytest.fixture
async def other_user(tmp_sqlite_backend: SQLiteBackend) -> User:
    """创建另一个用户"""
    return await tmp_sqlite_backend.create_user(UserCreate(username="other"))


# =====================================================================
# D1 — 系统内置预设
# =====================================================================


class TestListBuiltinPresets:
    """D1 系统内置预设"""

    async def test_list_builtin_presets(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
    ):
        await tmp_sqlite_backend.create_preset(
            PresetCreate(
                user_id=None,
                name="翻译助手",
                system_prompt="你是一个翻译助手",
                is_builtin=True,
            ),
        )
        presets = await mgr.list_builtin_presets()
        assert len(presets) == 1
        assert presets[0].name == "翻译助手"
        assert presets[0].is_builtin is True

    async def test_builtin_and_user_presets_separate(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        user_preset: None,
    ):
        """内置预设列表不应包含用户自定义预设"""
        await tmp_sqlite_backend.create_preset(
            PresetCreate(
                user_id=None,
                name="通用助手",
                system_prompt="你是一个有用的助手",
                is_builtin=True,
            ),
        )
        presets = await mgr.list_builtin_presets()
        assert len(presets) == 1
        assert all(p.is_builtin for p in presets)


# =====================================================================
# D2/D4 — 用户自定义预设列表
# =====================================================================


class TestListUserPresets:
    """D2/D4 用户自定义预设列表"""

    async def test_list_user_presets(self, mgr: PresetManager, user_preset: None):
        await mgr.create_preset(name="写作助手", system_prompt="你是一个写作助手")
        presets = await mgr.list_user_presets()
        assert len(presets) == 2

    async def test_list_user_presets_excludes_others(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        other_user: User,
    ):
        """其他用户的预设不应出现在当前用户列表中"""
        await mgr.create_preset(name="我的预设", system_prompt="助手")
        other_mgr = PresetManager(
            backend=tmp_sqlite_backend,
            user_id=other_user.id,
        )
        await other_mgr.create_preset(name="他人的预设", system_prompt="助手")
        presets = await mgr.list_user_presets()
        assert len(presets) == 1
        assert presets[0].name == "我的预设"


# =====================================================================
# D2 — 创建预设
# =====================================================================


class TestCreatePreset:
    """D2 创建自定义预设"""

    async def test_create_preset_success(self, mgr: PresetManager):
        preset = await mgr.create_preset(
            name="代码专家",
            system_prompt="你是一个代码专家",
            description="擅长代码审查",
        )
        assert preset.id == 1
        assert preset.name == "代码专家"
        assert preset.description == "擅长代码审查"
        assert preset.is_builtin is False

    async def test_create_preset_no_description(self, mgr: PresetManager):
        preset = await mgr.create_preset(
            name="简单预设",
            system_prompt="你是一个助手",
        )
        assert preset.description is None


# =====================================================================
# D3 — 按 ID 获取预设
# =====================================================================


class TestGetPreset:
    """D3 获取预设（不分归属）"""

    async def test_get_preset_by_id(
        self,
        mgr: PresetManager,
        user_preset: None,
    ):
        preset = await mgr.get_preset(1)
        assert preset is not None
        assert preset.name == "代码专家"

    async def test_get_preset_nonexistent_returns_none(self, mgr: PresetManager):
        assert await mgr.get_preset(999) is None

    async def test_get_builtin_preset(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        builtin_preset: None,
    ):
        """内置预设也可被查询到"""
        preset = await mgr.get_preset(1)
        assert preset is not None
        assert preset.is_builtin is True


# =====================================================================
# D2 — 更新预设
# =====================================================================


class TestUpdatePreset:
    """D2 更新预设"""

    async def test_update_preset_success(
        self,
        mgr: PresetManager,
        user_preset: None,
    ):
        updated = await mgr.update_preset(
            preset_id=1,
            name="代码大师",
            description="精通各类编程语言",
            system_prompt="你是一位代码大师",
        )
        assert updated.name == "代码大师"
        assert updated.description == "精通各类编程语言"

    async def test_update_builtin_preset_raises(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        builtin_preset: None,
    ):
        with pytest.raises(ValueError, match="内置预设不可编辑或删除"):
            await mgr.update_preset(
                preset_id=1,
                name="hack",
                description=None,
                system_prompt="hack",
            )

    async def test_update_other_user_preset_raises(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        other_user: User,
    ):
        """用户 A 不能更新用户 B 的预设"""
        other_mgr = PresetManager(
            backend=tmp_sqlite_backend,
            user_id=other_user.id,
        )
        await other_mgr.create_preset(
            name="他人的预设",
            system_prompt="助手",
        )
        with pytest.raises(ValueError, match="无权操作其他用户的预设"):
            await mgr.update_preset(
                preset_id=1,
                name="hack",
                description=None,
                system_prompt="hack",
            )

    async def test_update_nonexistent_preset_raises(self, mgr: PresetManager):
        with pytest.raises(ValueError, match="不存在"):
            await mgr.update_preset(
                preset_id=999,
                name="x",
                description=None,
                system_prompt="x",
            )


# =====================================================================
# D2 — 删除预设
# =====================================================================


class TestDeletePreset:
    """D2 删除预设"""

    async def test_delete_preset_success(
        self,
        mgr: PresetManager,
        user_preset: None,
    ):
        await mgr.delete_preset(1)
        assert await mgr.get_preset(1) is None

    async def test_delete_builtin_preset_raises(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        builtin_preset: None,
    ):
        with pytest.raises(ValueError, match="内置预设不可编辑或删除"):
            await mgr.delete_preset(1)

    async def test_delete_other_user_preset_raises(
        self,
        mgr: PresetManager,
        tmp_sqlite_backend: SQLiteBackend,
        other_user: User,
    ):
        other_mgr = PresetManager(
            backend=tmp_sqlite_backend,
            user_id=other_user.id,
        )
        await other_mgr.create_preset(
            name="他人的预设",
            system_prompt="助手",
        )
        with pytest.raises(ValueError, match="无权操作其他用户的预设"):
            await mgr.delete_preset(1)

    async def test_delete_nonexistent_preset_raises(self, mgr: PresetManager):
        with pytest.raises(ValueError, match="不存在"):
            await mgr.delete_preset(999)


# =====================================================================
# D1 — sync_builtin_presets 启动同步逻辑
# =====================================================================


class TestSyncBuiltinPresets:
    """sync_builtin_presets 全量同步测试"""

    _YAML_CONTENT = {
        "presets": [
            {
                "slug": "translator",
                "name": "翻译助手",
                "description": "中英互译",
                "system_prompt": "你是一个翻译助手",
            },
        ],
    }

    @pytest.fixture
    def yaml_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "presets.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(self._YAML_CONTENT, f, allow_unicode=True)
        return p

    async def test_sync_inserts_builtin_presets(
        self,
        tmp_sqlite_backend: SQLiteBackend,
        yaml_file: Path,
    ):
        """首次同步：YAML 中的预设应被插入数据库"""
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        presets = await tmp_sqlite_backend.get_builtin_presets()
        assert len(presets) == 1
        assert presets[0].slug == "translator"
        assert presets[0].is_builtin is True

    async def test_sync_idempotent(
        self,
        tmp_sqlite_backend: SQLiteBackend,
        yaml_file: Path,
    ):
        """重复同步不应重复插入"""
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        presets = await tmp_sqlite_backend.get_builtin_presets()
        assert len(presets) == 1

    async def test_sync_updates_changed_prompt(
        self,
        tmp_sqlite_backend: SQLiteBackend,
        yaml_file: Path,
    ):
        """YAML 中修改 system_prompt 后触发 UPDATE"""
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)

        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "presets": [
                        {
                            "slug": "translator",
                            "name": "翻译助手",
                            "description": "中英互译（新版）",
                            "system_prompt": "你是一个更好的翻译助手（新版）",
                        },
                    ],
                },
                f,
                allow_unicode=True,
            )
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        presets = await tmp_sqlite_backend.get_builtin_presets()
        assert len(presets) == 1
        assert presets[0].system_prompt == "你是一个更好的翻译助手（新版）"
        assert presets[0].description == "中英互译（新版）"

    async def test_sync_deletes_removed_preset(
        self,
        tmp_sqlite_backend: SQLiteBackend,
        yaml_file: Path,
    ):
        """YAML 中删除预设后，DB 中对应记录应被删除"""
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump({"presets": []}, f)
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        presets = await tmp_sqlite_backend.get_builtin_presets()
        assert len(presets) == 0

    async def test_sync_delete_clears_session_reference(
        self,
        tmp_sqlite_backend: SQLiteBackend,
        yaml_file: Path,
        test_user: User,
    ):
        """删除内置预设时，引用该预设的会话 preset_id 应被置 NULL"""
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)
        presets = await tmp_sqlite_backend.get_builtin_presets()
        preset_id = presets[0].id

        session = await tmp_sqlite_backend.create_session(
            SessionCreate(
                user_id=test_user.id,
                title="测试会话",
                model_name="gpt-4o",
                preset_id=preset_id,
            ),
        )
        assert session.preset_id == preset_id

        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump({"presets": []}, f)
        await PresetManager.sync_builtin_presets(tmp_sqlite_backend, yaml_path=yaml_file)

        reloaded = await tmp_sqlite_backend.get_session(session.id)
        assert reloaded is not None
        assert reloaded.preset_id is None
        assert await tmp_sqlite_backend.get_preset(preset_id) is None
