#!/usr/bin/env python3
"""学费计价器：安卓常驻通知（Termux）。每分钟算一次学费已烧掉多少，更新通知栏。"""
import json, os, subprocess, time
from datetime import datetime

TZ = "Asia/Shanghai"          # 时区，在国内不用改
INTERVAL = 60                 # 刷新间隔（秒）
DATA = os.path.expanduser("~/tuition/schedule.json")
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

os.environ["TZ"] = TZ
time.tzset()


def ts(d, t):
    return datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M").timestamp()


def label(d):
    x = datetime.strptime(d, "%Y-%m-%d")
    return f"{x.month}月{x.day}日 {WEEK[x.weekday()]}"


def rng(a, b):
    return f"第 {a} 节" if a == b else f"第 {a}–{b} 节"


def build(st):
    courses = {c["id"]: c for c in st.get("courses", [])}
    periods = st["periods"]
    blocks, sessions = {}, []
    for d in sorted(st.get("slots", {})):
        day = st["slots"][d] or {}
        cur, lst = None, []
        for p in range(1, 14):
            cid = day.get(str(p))
            if cid not in courses:
                cid = None
            if cid:
                blocks[cid] = blocks.get(cid, 0) + 1
            if cid and cur and cur["cid"] == cid and cur["to"] == p - 1:
                cur["to"] = p
            else:
                if cur:
                    lst.append(cur)
                cur = {"date": d, "cid": cid, "from": p, "to": p} if cid else None
        if cur:
            lst.append(cur)
        for s in lst:
            s["start"] = ts(d, periods[s["from"] - 1][0])
            s["end"] = ts(d, periods[s["to"] - 1][1])
            s["n"] = s["to"] - s["from"] + 1
        sessions += lst
    sessions.sort(key=lambda s: s["start"])
    per = {cid: courses[cid]["credits"] * st.get("perCredit", 120) / n for cid, n in blocks.items()}
    for s in sessions:
        s["v"] = per[s["cid"]] * s["n"]
        s["name"] = courses[s["cid"]]["name"]
        s["t0"] = periods[s["from"] - 1][0]
    return sessions


def message(st):
    now = time.time()
    sessions = build(st)
    if not sessions:
        return "学费计价器", "还没有课。先在网页里排课，复制课表，再运行 tuition-sync。"
    spent = left = 0.0
    current = nxt = None
    for s in sessions:
        if now >= s["end"]:
            spent += s["v"]
        elif now >= s["start"]:
            f = (now - s["start"]) / (s["end"] - s["start"])
            spent += s["v"] * f
            left += s["v"] * (1 - f)
            current = (s, f)
        else:
            left += s["v"]
            nxt = nxt or s
    total = spent + left
    title = f"学费已烧 ¥{spent:.2f} / ¥{total:.2f}"
    if current:
        s, f = current
        mins = int((now - s["start"]) // 60)
        dur = round((s["end"] - s["start"]) / 60)
        body = f"🔥 正在烧：{s['name']} {rng(s['from'], s['to'])}，已过 {mins}/{dur} 分钟，这节已烧 ¥{s['v'] * f:.2f} / ¥{s['v']:.2f}"
    elif nxt:
        diff = int(nxt["start"] - now)
        d, h, m = diff // 86400, diff % 86400 // 3600, diff % 3600 // 60
        wait = (f"{d} 天 " if d else "") + (f"{h} 小时 " if d or h else "") + f"{m} 分"
        body = f"下一节：{nxt['name']} {label(nxt['date'])} {nxt['t0']}，还有 {wait}，到点接着烧 ¥{nxt['v']:.2f}"
    else:
        body = "这学期的学费烧完了。"
    return title, body


def notify(title, body):
    subprocess.run([
        "termux-notification", "--id", "tuition", "--ongoing", "--alert-once",
        "--priority", "low", "--icon", "whatshot",
        "--title", title, "--content", body,
        "--button1", "停止", "--button1-action", PREFIX + "/bin/tuition-stop",
    ], check=False)


def main():
    while True:
        try:
            with open(DATA, encoding="utf-8") as fh:
                st = json.load(fh)
            title, body = message(st)
        except FileNotFoundError:
            title, body = "学费计价器", "还没有课表。在网页里点“复制课表”，再到 Termux 运行 tuition-sync。"
        except Exception as e:  # 课表损坏时提示，不退出
            title, body = "学费计价器", f"课表读不出来（{e}），重新复制课表后运行 tuition-sync。"
        notify(title, body)
        time.sleep(INTERVAL - time.time() % INTERVAL)


if __name__ == "__main__":
    main()
