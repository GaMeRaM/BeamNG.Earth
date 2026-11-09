"""Publish completed tile files without doing filesystem work on the asyncio loop."""
import asyncio
import logging
import os

import matslots
import staging

log = logging.getLogger('earthd.tilepublish')


def send(conn, message, files=None, valid=None):
    server = getattr(conn, 's', None)
    # Small protocol-only callers/test doubles have no live session pool.
    if server is None or not hasattr(server, 'slot_serial'):
        directory = getattr(server, 'out_dir', None)
        if directory and message.get('path'):
            data = staging.inline_json(directory, message['path'])
            if data is not None:
                message['data'] = data
        pool = getattr(server, 'pool_shapes', None)
        if pool and files:
            slots = pool(conn, files)
            if slots:
                message['slots'] = slots
        conn.send(message)
        return
    previous = getattr(conn, '_tile_publication', None)

    async def publish():
        if previous is not None:
            try:
                await asyncio.shield(previous)
            except Exception:
                pass  # a failed tile does not suppress every later publication
        def live():
            lease = getattr(conn, 'lease', None)
            return not getattr(conn, 'closing', False) and (lease is None or lease.connection is conn) and (valid is None or valid())
        if not live():
            return
        owners = getattr(server, '_publishing_owners', None)
        if owners is None:
            owners = server._publishing_owners = set()
        reserved = []
        try:
            if server.far_format == 'cdae':
                for what, filename in (files or {}).items():
                    owner = ('shape', next(server.slot_serial))
                    name = server.matslots.take(owner)
                    owners.add(owner)
                    reserved.append((what, filename, owner, name, next(server.slot_serial)))
            def prepare():
                data = staging.inline_json(server.out_dir, message['path']) if message.get('path') else None
                placed = []
                for what, filename, owner, name, serial in reserved:
                    slot = matslots.MatSlots.file(name)
                    try:
                        matslots.place(os.path.join(server.out_dir, filename), os.path.join(server.out_dir, slot))
                    except OSError as error:
                        log.debug('pooled shape %s: %s', filename, error)
                    else:
                        placed.append((what, name, slot, serial))
                return data, placed
            work = asyncio.get_running_loop().run_in_executor(None, prepare)
            try:
                data, placed = await asyncio.shield(work)
            except asyncio.CancelledError:
                # A cancelled coroutine cannot stop a file syscall. Keep the
                # reserved paths owned until that worker has stopped writing.
                await asyncio.shield(work)
                raise
            if not live():
                return
            if data is not None:
                message['data'] = data
            if placed:
                message['slots'] = {what: [f'{server.vfs_dir}/{slot}', serial] for what, name, slot, serial in placed}
                for what, name, slot, serial in placed:
                    conn.slot_holds[matslots.MatSlots.number(name)] = serial
            conn.send(message)
        finally:
            for what, filename, owner, name, serial in reserved:
                owners.discard(owner)
                server.matslots.release(owner)

    task = asyncio.create_task(publish())
    conn._tile_publication = task
    def done(future):
        if conn._tile_publication is future:
            conn._tile_publication = None
        if not future.cancelled() and future.exception() is not None:
            log.error('tile publication failed', exc_info=future.exception())
    task.add_done_callback(done)
