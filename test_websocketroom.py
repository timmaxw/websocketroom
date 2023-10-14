import argparse
import json
import logging

import trio
import trio_websocket

from websocketroom import Server

async def test_websocketroom():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(Server(host="localhost", port=8910).main)
        await run_test("localhost", 8910, False)
        nursery.cancel_scope.cancel()

async def run_test(host: str, port: int, ssl: bool):
    async with (
        trio_websocket.open_websocket(host, port, "/websocketroom/room1/conn1", use_ssl=ssl) as conn1,
    ):
        msg = json.loads(await conn1.get_message())
        assert msg == {"websocketroom": {"members": ["conn1"]}}

        await conn1.send_message(json.dumps("nobody will receive this message"))

        async with trio_websocket.open_websocket(host, port, "/websocketroom/room1/conn2", use_ssl=ssl) as conn2:
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ssl", action="store_true", default=False)
    args = parser.parse_args()

    trio.run(run_test, args.host, args.port, args.ssl)
