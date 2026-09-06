"""Ask every character created by a batch its answer-key questions over the /sdk chat socket.

    pip install "python-socketio[asyncio_client]"
    python probe.py <base_url> <api_key> <batch_id> [max_questions_per_character]

Reads manifest.json next to this file, maps the batch's customIds to characterIds,
opens one text-only session per character, and prints PASS/FAIL per question by
case-insensitive substring match. Results are written to probe.results.json.
"""
import asyncio
import json
import os
import re
import sys
import time
import urllib.request

import socketio

BASE, API_KEY, BATCH_ID = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
MAXQ = int(sys.argv[4]) if len(sys.argv) > 4 else 99
HERE = os.path.dirname(os.path.abspath(__file__))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fetch_batch():
    req = urllib.request.Request(f"{BASE}/api/v1/characters/batch/{BATCH_ID}", headers={"X-API-Key": API_KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


async def ask(character_id, questions, player_id):
    sio = socketio.AsyncClient(reconnection=False)
    done, auth = asyncio.Event(), asyncio.Event()
    state = {"text": "", "auth_err": None}
    ns = "/sdk"

    @sio.on("session_info", namespace=ns)
    async def _si(d):
        auth.set()

    @sio.on("auth_error", namespace=ns)
    async def _ae(d):
        state["auth_err"] = d
        auth.set()

    @sio.on("bot_response", namespace=ns)
    async def _br(d):
        if d.get("is_final"):
            state["text"] = d.get("text") or state["text"]
            done.set()
        else:
            state["text"] += d.get("partial") or ""

    @sio.on("error", namespace=ns)
    async def _er(d):
        state["text"] = f"<error {d}>"
        done.set()

    await sio.connect(BASE, namespaces=[ns], transports=["websocket"],
                      auth={"api_key": API_KEY, "character_id": character_id,
                            "player_id": player_id, "audio_sample_rate": 24000})
    await asyncio.wait_for(auth.wait(), 20)
    if state["auth_err"]:
        await sio.disconnect()
        return [(q, f"<auth_error {state['auth_err']}>", 0.0) for q in questions]
    out = []
    for q in questions:
        state["text"] = ""
        done.clear()
        t0 = time.time()
        await sio.emit("text", {"text": q, "textOnly": True}, namespace=ns)
        try:
            await asyncio.wait_for(done.wait(), 90)
        except asyncio.TimeoutError:
            state["text"] = "<timeout>"
        out.append((q, state["text"], time.time() - t0))
    await sio.disconnect()
    return out


async def main():
    batch = fetch_batch()
    if "items" not in batch:
        sys.exit(f"batch {BATCH_ID}: no items in response ({batch.get('status')})")
    ids = {it["customId"]: it.get("characterId") for it in batch["items"] if it.get("characterId")}
    manifest = json.load(open(os.path.join(HERE, "manifest.json"), encoding="utf-8"))
    results, passed, failed = [], 0, 0
    for ch in manifest["characters"]:
        cid = ids.get(ch["customId"])
        if not cid:
            print(f"SKIP {ch['customId']}: not in this batch")
            continue
        checks = ch["retrieval_checks"][:MAXQ]
        answers = await ask(cid, [c["question"] for c in checks], f"probe-{ch['customId']}")
        for c, (q, a, dt) in zip(checks, answers):
            ok = f" {norm(c['expect'])} " in f" {norm(a)} "
            passed += ok
            failed += not ok
            src = c["source_file"].split("/")[-1]
            print(f"{'PASS' if ok else 'FAIL'} {ch['customId']:<26} {dt:5.1f}s [{src}] {q} -> expect={c['expect']!r} got={a[:140]!r}", flush=True)
            results.append({**c, "customId": ch["customId"], "characterId": cid, "answer": a, "seconds": dt, "pass": ok})
    json.dump(results, open(os.path.join(HERE, "probe.results.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"TOTAL pass={passed} fail={failed}")


asyncio.run(main())
