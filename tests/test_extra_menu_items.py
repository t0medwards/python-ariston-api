"""ExtraMenuItemNames: retried after a failure, given up only if never supported"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ariston.ariston_api import ConnectionException
from ariston.galevo_device import EXTRA_MENU_ITEMS_MAX_FAILURES, AristonGalevoDevice

ITEMS = [{"id": 125, "value": 6.0}]


def make_device(extra_replies):
    """A device whose extra menu items request returns each of extra_replies in turn"""
    api = MagicMock()
    api.async_get_properties = AsyncMock(return_value={})

    async def get_menu_items(gw, menu_items=None):
        if menu_items is None:
            return []
        reply = extra_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    api.async_get_menu_items = AsyncMock(side_effect=get_menu_items)
    device = AristonGalevoDevice(api, {"gw": "GW"})
    device.features = {"zones": []}
    return device


def update(device, times=1):
    with patch.object(AristonGalevoDevice, "_update_state"):
        for _ in range(times):
            asyncio.run(device.async_update_state())


class ExtraMenuItemsTest(unittest.TestCase):
    def test_failure_after_success_is_retried(self):
        device = make_device([ITEMS, ConnectionException(500), ITEMS])
        update(device)
        self.assertEqual(device.extra_menu_items, ITEMS)
        update(device)
        self.assertEqual(device.extra_menu_items, [])
        self.assertTrue(device.extra_menu_items_supported)
        update(device)
        self.assertEqual(device.extra_menu_items, ITEMS)

    def test_many_failures_after_success_keep_retrying(self):
        replies = [ITEMS] + [ConnectionException(500)] * (EXTRA_MENU_ITEMS_MAX_FAILURES + 2)
        device = make_device(replies)
        update(device, EXTRA_MENU_ITEMS_MAX_FAILURES + 3)
        self.assertTrue(device.extra_menu_items_supported)

    def test_never_supported_gives_up(self):
        device = make_device([ConnectionException(500)] * EXTRA_MENU_ITEMS_MAX_FAILURES)
        update(device, EXTRA_MENU_ITEMS_MAX_FAILURES - 1)
        self.assertTrue(device.extra_menu_items_supported)
        update(device)
        self.assertFalse(device.extra_menu_items_supported)
        # No further extra requests once given up
        update(device)
        self.assertEqual(device.api.async_get_menu_items.await_count, 2 * EXTRA_MENU_ITEMS_MAX_FAILURES + 1)

    def test_failure_at_start_then_success(self):
        device = make_device([ConnectionException(500), ITEMS])
        update(device, 2)
        self.assertEqual(device.extra_menu_items, ITEMS)
        self.assertTrue(device.extra_menu_items_supported)


if __name__ == "__main__":
    unittest.main()
