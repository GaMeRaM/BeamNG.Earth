import asyncio
import itertools
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matslots
import tilepublish


class PublicationTest(unittest.IsolatedAsyncioTestCase):
    async def test_slow_io_keeps_loop_live_and_messages_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            entered, release = threading.Event(), threading.Event()
            main = threading.get_ident()
            server = SimpleNamespace(out_dir=directory, vfs_dir='/vfs', far_format='cdae', slot_serial=itertools.count())
            conn = SimpleNamespace(s=server, closing=False, slot_holds={}, sent=[])
            conn.send = conn.sent.append
            server.matslots = matslots.MatSlots('test', held=lambda n: n in conn.slot_holds)
            Path(directory, 'shape.cdae').write_bytes(b'shape')
            def read(*args):
                self.assertNotEqual(threading.get_ident(), main)
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('test worker not released')
                return {'ready': True}
            with patch('staging.inline_json', side_effect=read):
                tilepublish.send(conn, {'type': 'first', 'path': 'one.json'}, {'road': 'shape.cdae'})
                first = conn._tile_publication
                tilepublish.send(conn, {'type': 'second', 'path': 'two.json'})
                last = conn._tile_publication
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    await asyncio.wait_for(asyncio.sleep(.01), .5)
                    self.assertEqual(conn.sent, [])
                    self.assertTrue(server._publishing_owners)
                finally:
                    release.set()
                await asyncio.wait_for(last, 3)
            self.assertEqual([m['type'] for m in conn.sent], ['first', 'second'])
            self.assertEqual(Path(directory, 'slot_00000.cdae').read_bytes(), b'shape')
            self.assertFalse(server._publishing_owners)
            self.assertTrue(conn.slot_holds)

    async def test_connection_replaced_during_io_releases_unpublished_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            entered, release = threading.Event(), threading.Event()
            server = SimpleNamespace(out_dir=directory, vfs_dir='/vfs', far_format='cdae', slot_serial=itertools.count())
            conn = SimpleNamespace(s=server, closing=False, slot_holds={}, sent=[])
            conn.send = conn.sent.append
            server.matslots = matslots.MatSlots('test', held=lambda n: n in conn.slot_holds)
            Path(directory, 'shape.cdae').write_bytes(b'shape')
            def read(*args):
                entered.set()
                release.wait(5)
            with patch('staging.inline_json', side_effect=read):
                tilepublish.send(conn, {'path': 'one.json'}, {'road': 'shape.cdae'})
                task = conn._tile_publication
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    conn.closing = True
                finally:
                    release.set()
                await asyncio.wait_for(task, 3)
            self.assertEqual(conn.sent, [])
            self.assertFalse(conn.slot_holds)
            self.assertFalse(server._publishing_owners)
            self.assertFalse(server.matslots.holders())

    async def test_cancel_does_not_recycle_a_slot_while_worker_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            entered, release = threading.Event(), threading.Event()
            server = SimpleNamespace(out_dir=directory, vfs_dir='/vfs', far_format='cdae', slot_serial=itertools.count())
            conn = SimpleNamespace(s=server, closing=False, slot_holds={}, sent=[])
            conn.send = conn.sent.append
            server.matslots = matslots.MatSlots('test', held=lambda n: n in conn.slot_holds)
            Path(directory, 'shape.cdae').write_bytes(b'shape')
            def read(*args):
                entered.set()
                release.wait(5)
            with patch('staging.inline_json', side_effect=read):
                tilepublish.send(conn, {'path': 'one.json'}, {'road': 'shape.cdae'})
                task = conn._tile_publication
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    task.cancel()
                    await asyncio.sleep(.01)
                    self.assertTrue(server._publishing_owners)
                    self.assertTrue(server.matslots.holders())
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertFalse(server._publishing_owners)
            self.assertFalse(server.matslots.holders())
            self.assertFalse(conn.sent)

    async def test_prune_directory_scan_does_not_block_the_loop(self):
        import earthd
        with tempfile.TemporaryDirectory() as directory:
            entered, release = threading.Event(), threading.Event()
            main = threading.get_ident()
            pruned = asyncio.Event()
            server = SimpleNamespace(anchors={1: object(), 2: object()}, _prune_scheduled=set(),
                out_dir=directory, cdae_dir=directory, prune_delay=0., prune_recheck=.01,
                held_anchors=lambda: set())
            def prune(keep_from, listing=None):
                self.assertEqual(threading.get_ident(), main)
                self.assertEqual(keep_from, 2)
                self.assertIn(directory, listing)
                pruned.set()
            server.prune = prune
            server.schedule_prune = lambda keep: earthd.Server.schedule_prune(server, keep)
            def listing(path):
                self.assertNotEqual(threading.get_ident(), main)
                entered.set()
                release.wait(5)
                return ['roads_1_0_0.json']
            with patch('earthd.os.listdir', side_effect=listing):
                server.schedule_prune(2)
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    await asyncio.wait_for(asyncio.sleep(.01), .5)
                    self.assertFalse(pruned.is_set())
                finally:
                    release.set()
                await asyncio.wait_for(pruned.wait(), 3)
            self.assertFalse(server._prune_scheduled)
