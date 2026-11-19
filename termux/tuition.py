#!/usr/bin/env python3
"""Your Tuition Fee is Burning🔥：安卓常驻通知（Termux）。
每分钟更新一次通知栏；开课前提醒；下课发扣款短信；每月 1 日发上月账单。"""
import json, os, random, subprocess, time
from datetime import datetime

TZ = "Asia/Shanghai"          # 时区，在国内不用改
INTERVAL = 60                 # 刷新间隔（秒）
DIR = os.path.expanduser("~/tuition")
DATA = os.path.join(DIR, "schedule.json")
LINES = os.path.join(DIR, "lines.json")
MEM = os.path.join(DIR, "state.json")
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TEA = 18
APP = "Your Tuition Fee is Burning🔥"
DEF = {"lang": "zh", "tail": "5532", "remind": 10, "sms": True}

os.environ["TZ"] = TZ
time.tzset()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, path)


def ts(d, t):
    return datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M").timestamp()


def label(d):
    x = datetime.strptime(d, "%Y-%m-%d")
    return f"{x.month}月{x.day}日 {WEEK[x.weekday()]}"


def rng(a, b, tight=False):
    if tight:
        return f"第{a}节" if a == b else f"第{a}–{b}节"
    return f"第 {a} 节" if a == b else f"第 {a}–{b} 节"


def wait_text(sec, en):
    m = max(1, -(-int(sec) // 60))
    d, h, mi = m // 1440, m % 1440 // 60, m % 60
    if en:
        return f"{d} day{'s' if d > 1 else ''}" if d else (f"{h} h" + (f" {mi} min" if mi else "") if h else f"{mi} min")
    return f"{d} 天" if d else (f"{h} 小时" + (f" {mi} 分钟" if mi else "") if h else f"{mi} 分钟")


def is_en(line):
    return not any("\u4e00" <= ch <= "\u9fff" for ch in line)


def fill(line, v):
    en = is_en(line)
    out = line
    for k, val in v.items():
        if k == "waitSec":
            continue
        out = out.replace("{" + k + "}", str(val))
    if "{wait}" in out:
        out = out.replace("{wait}", wait_text(v.get("waitSec", 0), en))
    return out


def build(st):
    courses = {c["id"]: c for c in st.get("courses", [])}
    periods = st["periods"]
    per_credit = st.get("perCredit", 120)
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
        for i, s in enumerate(lst):
            s["start"] = ts(d, periods[s["from"] - 1][0])
            s["end"] = ts(d, periods[s["to"] - 1][1])
            s["n"] = s["to"] - s["from"] + 1
            s["ord"] = i
            s["key"] = f"{d}_{s['cid']}_{s['from']}"
        sessions += lst
    sessions.sort(key=lambda s: s["start"])
    cum = {}
    for s in sessions:
        c = courses[s["cid"]]
        s["v"] = c["credits"] * per_credit / blocks[s["cid"]] * s["n"]
        s["name"] = c["name"]
        s["t0"] = periods[s["from"] - 1][0]
        cum[s["cid"]] = cum.get(s["cid"], 0) + s["v"]
        s["bal"] = max(0.0, c["credits"] * per_credit - cum[s["cid"]])
    return sessions


def settings(st):
    s = dict(DEF)
    s.update({k: v for k, v in (st.get("settings") or {}).items() if k in DEF})
    return s


def pool(lines, lang, cat):
    if lang == "off" or not lines:
        return []
    if lang == "mix":
        return lines.get("zh", {}).get(cat, []) + lines.get("yue", {}).get(cat, []) + lines.get("en", {}).get(cat, [])
    return lines.get(lang, lines.get("zh", {})).get(cat, [])


def pick(mem, lines, lang, cat):
    """当天不重复地挑一句，返回模板。"""
    p = pool(lines, lang, cat)
    if not p:
        return None
    day = datetime.now().strftime("%Y-%m-%d")
    used = mem.setdefault("roast", {})
    for k in list(used):
        if not k.startswith(day):
            del used[k]
    key = f"{day}|{lang}|{cat}"
    seen = used.setdefault(key, [])
    left = [i for i in range(len(p)) if i not in seen] or list(range(len(p)))
    if len(left) == len(p):
        seen.clear()
    i = random.choice(left)
    seen.append(i)
    return p[i]


def notify(nid, title, body, *extra):
    subprocess.run(["termux-notification", "--id", nid, "--title", title, "--content", body, *extra], check=False)


def sms_text(s, cfg, t_end):
    d = datetime.fromtimestamp(t_end)
    if cfg["lang"] == "en":
        return (f"[Zhejiang University] Your tuition account ending {cfg['tail']} was debited CNY {s['v']:.2f} "
                f"on {MON[d.month - 1]} {d.day} at {d:%H:%M} for {s['name']}, periods {s['from']}–{s['to']}. "
                f"Balance: CNY {s['bal']:.2f}.")
    return (f"【浙江大学】您尾号{cfg['tail']}的学费账户于{d.month}月{d.day}日{d:%H:%M}支出人民币{s['v']:.2f}元，"
            f"用途：{s['name']}{rng(s['from'], s['to'], True)}，余额{s['bal']:.2f}元。")


def tick(st, lines, mem, first):
    now = time.time()
    cfg = settings(st)
    en = cfg["lang"] == "en"
    sessions = build(st)
    if not sessions:
        notify("tuition", APP, "还没有课。先在应用里排课，点“复制课表”，再运行 tuition-sync。",
               "--ongoing", "--alert-once", "--priority", "low", "--icon", "whatshot")
        return

    # 下课扣款短信
    sent = set(mem.setdefault("sms", []))
    for s in sessions:
        if now >= s["end"] and s["key"] not in sent:
            sent.add(s["key"])
            if not first and cfg["sms"] and now - s["end"] < 12 * 3600:
                notify("sms_" + s["key"], "Zhejiang University" if en else "浙江大学", sms_text(s, cfg, s["end"]),
                       "--group", "tuition-sms", "--priority", "default", "--sound", "--icon", "account_balance")
    mem["sms"] = sorted(sent)

    # 开课前提醒
    pre_done = set(mem.setdefault("pre", []))
    if cfg["remind"]:
        for s in sessions:
            if s["start"] - cfg["remind"] * 60 <= now < s["start"] and s["key"] not in pre_done:
                pre_done.add(s["key"])
                v = {"course": s["name"], "amount": f"{s['v']:.2f}", "tea": f"{s['v'] / TEA:.1f}",
                     "perMin": f"{s['v'] / ((s['end'] - s['start']) / 60):.2f}", "waitSec": s["start"] - now}
                tpl = pick(mem, lines, cfg["lang"], "pre")
                title = (f"{s['name']} in {wait_text(s['start'] - now, True)}" if en
                         else f"{s['name']} {wait_text(s['start'] - now, False)}后开课")
                body = fill(tpl, v) if tpl else (f"{s['t0']} starts, ¥{s['v']:.2f} begins to burn." if en
                                                 else f"{s['t0']} 开课，¥{s['v']:.2f} 准备开烧。")
                notify("pre", title, body, "--priority", "high", "--sound", "--vibrate", "300,150,300", "--icon", "alarm")
    mem["pre"] = sorted(pre_done)[-200:]

    # 每月 1 日 9 点后发上月账单
    dnow = datetime.now()
    prev_y, prev_m = (dnow.year, dnow.month - 1) if dnow.month > 1 else (dnow.year - 1, 12)
    prev = f"{prev_y}-{prev_m:02d}"
    stmts = set(mem.setdefault("stmt", []))
    if prev not in stmts and (first or dnow.hour >= 9 or dnow.day > 1):
        stmts.add(prev)
        bill = [s for s in sessions if now >= s["end"] and datetime.fromtimestamp(s["end"]).strftime("%Y-%m") == prev]
        if bill and not first:
            amt = sum(s["v"] for s in bill)
            if en:
                body = (f"[Zhejiang University] Your {MON[prev_m - 1]} {prev_y} tuition statement is ready: "
                        f"CNY {amt:.2f} across {len(bill)} charges. Minimum payment: show up to class.")
            else:
                body = (f"【浙江大学】您{prev_y}年{prev_m}月学费账单已出：本期消费人民币{amt:.2f}元，共{len(bill)}笔，"
                        f"最低还款额0.00元，还款方式：按时上课。详情请打开应用查看。")
            notify("stmt_" + prev, "Zhejiang University" if en else "浙江大学", body,
                   "--priority", "default", "--sound", "--icon", "receipt")
    mem["stmt"] = sorted(stmts)

    # 常驻通知
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
    title = f"Tuition burned ¥{spent:.2f} / ¥{total:.2f}" if en else f"学费已烧 ¥{spent:.2f} / ¥{total:.2f}"
    if current:
        s, f = current
        mins = int((now - s["start"]) // 60)
        dur = round((s["end"] - s["start"]) / 60)
        burned = s["v"] * f
        facts = (f"🔥 {s['name']} {rng(s['from'], s['to'])}, {mins}/{dur} min, ¥{burned:.2f} / ¥{s['v']:.2f} burned" if en
                 else f"🔥 正在烧：{s['name']} {rng(s['from'], s['to'])}，已过 {mins}/{dur} 分钟，这节已烧 ¥{burned:.2f} / ¥{s['v']:.2f}")
        slot = f"{s['key']}#{mins // 15}#{cfg['lang']}"
        live = mem.setdefault("live", {})
        if live.get("slot") != slot:
            live["slot"] = slot
            live["tpl"] = pick(mem, lines, cfg["lang"], "live")
        tpl = live.get("tpl")
        v = {"course": s["name"], "amount": f"{s['v']:.2f}", "burned": f"{burned:.2f}", "left": f"{s['v'] - burned:.2f}",
             "pct": f"{int(f * 100)}%", "btea": f"{burned / TEA:.1f}", "tea": f"{s['v'] / TEA:.1f}",
             "perMin": f"{s['v'] / dur:.2f}"}
        body = (fill(tpl, v) + "\n" + facts) if tpl else facts
    elif nxt:
        diff = nxt["start"] - now
        body = (f"Next: {nxt['name']} {label(nxt['date'])} {nxt['t0']}, in {wait_text(diff, True)}, ¥{nxt['v']:.2f} to burn" if en
                else f"下一节：{nxt['name']} {label(nxt['date'])} {nxt['t0']}，还有 {wait_text(diff, False)}，到点接着烧 ¥{nxt['v']:.2f}")
    else:
        body = "All tuition for the term has burned." if en else "这学期的学费烧完了。"
    notify("tuition", title, body, "--ongoing", "--alert-once", "--priority", "low", "--icon", "whatshot",
           "--button1", "停止" if not en else "Stop", "--button1-action", PREFIX + "/bin/tuition-stop")


def main():
    first = not os.path.exists(MEM)
    mem = load(MEM, {})
    while True:
        st = load(DATA, None)
        if st is None:
            notify("tuition", APP, "还没有课表。在应用里点“复制课表”，再到 Termux 运行 tuition-sync。",
                   "--ongoing", "--alert-once", "--priority", "low", "--icon", "whatshot")
        else:
            try:
                tick(st, load(LINES, {}), mem, first)
                first = False
                save(MEM, mem)
            except Exception as e:  # 课表损坏时提示，不退出
                notify("tuition", APP, f"课表读不出来（{e}），重新复制课表后运行 tuition-sync。",
                       "--ongoing", "--alert-once", "--priority", "low")
        time.sleep(INTERVAL - time.time() % INTERVAL)


if __name__ == "__main__":
    main()
