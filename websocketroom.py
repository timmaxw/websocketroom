import argparse
import logging
import json
import re

import trio
import trio.testing
import trio_websocket

class Server:
    def __init__(self, *, host: str, port: int):
        self.host = host
        self.port = port
        self.rooms: dict[str, dict[str, trio.MemorySendChannel]] = {}

    async def main(self):
        logging.info(f"server starting on port {self.port}")
        try:
            await trio_websocket.serve_websocket(self.handle_connection, self.host, self.port, ssl_context=None)
        finally:
            logging.info(f"server stopping")

    async def handle_connection(self, request: trio_websocket.WebSocketRequest) -> None:
        logging.info(f"connection opened {request.path!r}")
        match = re.fullmatch(r"/websocketroom/(\w+)/(\w+)", request.path)
        if not match:
            logging.error(f"connection rejected: bad path")
            await request.reject(404, body=f"bad path: {request.path!r}".encode("utf8"))
            return
        room_id = match.group(1)
        my_name = match.group(2)

        my_send_channel, my_receive_channel = trio.open_memory_channel(float("inf"))

        room = self.rooms.setdefault(room_id, {})
        if my_name in room:
            logging.error(f"connection rejected: name conflict")
            await request.reject(400, body=f"name {my_name!r} is already taken".encode("utf8"))
            return

        with trio.testing.assert_no_checkpoints():
            assert my_name not in room
            room[my_name] = my_send_channel
            enter_message = json.dumps({
                "websocketroom": {
                    "members": sorted(room.keys()),
                }
            })
            for peer_or_my_send_channel in room.values():
                peer_or_my_send_channel.send_nowait(enter_message)

        my_conn: trio_websocket.WebSocketConnection = await request.accept()

        async with trio.open_nursery() as nursery:
            async def send_loop():
                async for message in my_receive_channel:
                    logging.debug(f"message to {request.path!r} ({len(message)} bytes)")
                    await my_conn.send_message(message)

            nursery.start_soon(send_loop)

            while True:
                try:
                    message = await my_conn.get_message()
                except trio_websocket.ConnectionClosed:
                    break
                logging.debug(f"message from {request.path!r} ({len(message)} bytes)")
                for peer_name, peer_send_channel in room.items():
                    if peer_name != my_name:
                        peer_send_channel.send_nowait(message)

            logging.info(f"connection closed {request.path!r}")

            nursery.cancel_scope.cancel()

        with trio.testing.assert_no_checkpoints():
            assert room[my_name] is my_send_channel
            del room[my_name]
            exit_message = json.dumps({
                "websocketroom": {
                    "members": sorted(room.keys()),
                }
            })
            for peer_send_channel in room.values():
                peer_send_channel.send_nowait(exit_message)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port)
    trio.run(server.main)
