#!/data/data/com.termux/files/usr/bin/bash
# 学费计价器：安装安卓常驻通知
# 用法：curl -fsSL <网址>/termux/install.sh | bash -s -- <网址>
set -e
BASE="${1%/}"
if [ -z "$BASE" ]; then echo "缺少网址。请从网页里复制完整的安装命令。"; exit 1; fi
B="$PREFIX/bin"

echo "1/3 安装 Python 和 Termux:API 工具……"
pkg update -y >/dev/null 2>&1 || true
pkg install -y python termux-api

echo "2/3 下载脚本……"
mkdir -p "$HOME/tuition"
curl -fsSL "$BASE/termux/tuition.py" -o "$HOME/tuition/tuition.py"

echo "3/3 创建命令……"
cat > "$B/tuition-start" <<'X'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f "tuition/tuition.py" >/dev/null 2>&1
termux-wake-lock
nohup python "$HOME/tuition/tuition.py" >/dev/null 2>&1 &
echo "常驻通知已开启，下拉通知栏就能看到。"
X
cat > "$B/tuition-stop" <<'X'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f "tuition/tuition.py" >/dev/null 2>&1
termux-notification-remove tuition
termux-wake-unlock
echo "常驻通知已关闭。"
X
cat > "$B/tuition-sync" <<'X'
#!/data/data/com.termux/files/usr/bin/bash
TMP="$HOME/tuition/schedule.json.tmp"
termux-clipboard-get > "$TMP"
if python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert 'courses' in d and 'slots' in d" "$TMP" 2>/dev/null; then
  mv "$TMP" "$HOME/tuition/schedule.json"
  echo "课表已更新。"
  tuition-start
else
  rm -f "$TMP"
  echo "剪贴板里不是课表。先回网页点“复制课表”，再运行 tuition-sync。"
  exit 1
fi
X
chmod +x "$B/tuition-start" "$B/tuition-stop" "$B/tuition-sync"
echo ""
echo "装好了。回网页点“复制课表”，再在这里运行：tuition-sync"
