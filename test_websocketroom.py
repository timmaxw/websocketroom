import json

import trio
import trio_websocket

from websocketroom import Server

PORT = 8910

async def test_websocketroom():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(Server(port=PORT).main)

        async with (
            trio_websocket.open_websocket("localhost", PORT, "/websocketroom/room1/conn1", use_ssl=False) as conn1,
        ):
            msg = json.loads(await conn1.get_message())
            assert msg == {"websocketroom": {"members": ["conn1"]}}

            await conn1.send_message(json.dumps("nobody will receive this message"))

            async with trio_websocket.open_websocket("localhost", PORT, "/websocketroom/room1/conn2", use_ssl=False) as conn2:
                msg = json.loads(await conn1.get_message())
                assert msg == {"websocketroom": {"members": ["conn1", "conn2"]}}

                msg = json.loads(await conn2.get_message())
                assert msg == {"websocketroom": {"members": ["conn1", "conn2"]}}

                await conn1.send_message(json.dumps("from conn1 to conn2"))
                msg = json.loads(await conn2.get_message())
                assert msg == "from conn1 to conn2"

                await conn2.send_message(json.dumps("from conn2 to conn1"))
                msg = json.loads(await conn1.get_message())
                assert msg == "from conn2 to conn1"

            msg = json.loads(await conn1.get_message())
            assert msg == {"websocketroom": {"members": ["conn1"]}}

        nursery.cancel_scope.cancel()