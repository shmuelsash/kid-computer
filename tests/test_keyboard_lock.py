"""The lock must swallow escape routes and pass ordinary keys through."""

from kidcomputer.keyboard_lock import (
    VK_APPS,
    VK_ESCAPE,
    VK_F4,
    VK_LWIN,
    VK_RWIN,
    VK_TAB,
    should_block,
)


def test_blocks_windows_keys() -> None:
    for vk in (VK_LWIN, VK_RWIN, VK_APPS):
        assert should_block(vk, alt_down=False, ctrl_down=False) is True


def test_blocks_alt_combos() -> None:
    assert should_block(VK_TAB, alt_down=True, ctrl_down=False) is True
    assert should_block(VK_F4, alt_down=True, ctrl_down=False) is True
    assert should_block(VK_ESCAPE, alt_down=True, ctrl_down=False) is True


def test_blocks_ctrl_escape() -> None:
    assert should_block(VK_ESCAPE, alt_down=False, ctrl_down=True) is True


def test_passes_ordinary_keys() -> None:
    # 'A' = 0x41. Plain letters, and even Tab without Alt, must pass through so
    # they can drive the on-screen fun.
    assert should_block(0x41, alt_down=False, ctrl_down=False) is False
    assert should_block(VK_TAB, alt_down=False, ctrl_down=False) is False
    assert should_block(VK_ESCAPE, alt_down=False, ctrl_down=False) is False
