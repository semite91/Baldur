"""Fake Recognition engine for Warning-host tests (issue W1, #13).

Prints frozen JSON-lines events on stdout like the real engine will.
Modes keep runs deterministic and fast; the harness kills infinite runs.
Only stdlib; nothing here touches hardware, models, or the network.
"""

import argparse
import json
import sys
import time


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="count",
                        choices=("count", "script", "malformed", "infinite", "spam",
                                 "cycle", "die-after"))
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()

    if args.mode == "count":
        for _ in range(args.count):
            emit("heartbeat", score=78)
            time.sleep(args.interval)
    elif args.mode == "script":
        emit("heartbeat", score=78)
        time.sleep(0.2)
        emit("bad_posture", score=64, dwell_s=10)
        time.sleep(0.2)
        emit("heartbeat", score=64)
        time.sleep(0.2)
        emit("recovered", score=82, dwell_s=3)
        time.sleep(0.2)
        emit("heartbeat", score=82)
    elif args.mode == "malformed":
        emit("heartbeat", score=78)
        print("this is not json{{{", flush=True)
        emit("heartbeat", score=78)
    elif args.mode == "spam":
        for index in range(200):
            print(f"diagnostic chatter {index}", file=sys.stderr, flush=True)
        for _ in range(5):
            emit("heartbeat", score=78)
    elif args.mode == "cycle":
        while True:
            emit("heartbeat", score=78)
            time.sleep(0.2)
            emit("bad_posture", score=64, dwell_s=10)
            time.sleep(3.0)
            emit("recovered", score=82, dwell_s=3)
            time.sleep(3.0)
    elif args.mode == "die-after":
        for _ in range(args.count):
            emit("heartbeat", score=78)
            time.sleep(args.interval)
        sys.exit(1)
    else:
        while True:
            emit("heartbeat", score=78)
            time.sleep(0.2)


if __name__ == "__main__":
    main()
