#!/bin/bash
# Состояние приёмника одной командой: жив ли бот, есть ли связь с Telegram,
# сколько собрано. Только читает — ничего не перезапускает и не чинит.
#
# Код возврата: 0 — бот жив, 1 — пульс протух или его нет.
# Порог протухания (300 с) совпадает с healthcheck.py.
set -uo pipefail

DIR="${EZS_INBOX_DIR:-/opt/ezs-inbox}"
CONTAINER="${EZS_INBOX_CONTAINER:-telegram-logger-bot}"
STALE_AFTER=300

now=$(date +%s)
rc=0

fmt_age() {           # секунды -> человекочитаемо
  local s=$1
  if   [ "$s" -lt 90 ];    then echo "${s} сек назад"
  elif [ "$s" -lt 5400 ];  then echo "$((s / 60)) мин назад"
  else                          echo "$((s / 3600)) ч назад"
  fi
}

# --- пульс ---
HEALTH="$DIR/data/health.json"
if [ ! -f "$HEALTH" ]; then
  echo "приёмник:         НЕТ ПУЛЬСА (файл $HEALTH отсутствует)"
  rc=1
else
  ts=$(python3 -c "import json;print(int(json.load(open('$HEALTH'))['ts']))" 2>/dev/null)
  if [ -z "$ts" ]; then
    echo "приёмник:         НЕТ ПУЛЬСА (файл нечитаем)"
    rc=1
  else
    a=$((now - ts))
    if [ "$a" -gt "$STALE_AFTER" ]; then
      echo "приёмник:         МЁРТВ — пульс $(fmt_age $a), порог ${STALE_AFTER} сек"
      rc=1
    else
      echo "приёмник:         жив (пульс $(fmt_age $a))"
    fi
    ok=$(python3 -c "
import json; h=json.load(open('$HEALTH'))
t=h.get('telegram_ok'); lo=h.get('last_ok'); le=h.get('last_error')
print('|'.join([str(t), str(int(lo)) if lo else '', (le or '')[:80]]))" 2>/dev/null)
    IFS='|' read -r t_ok t_last t_err <<< "$ok"
    if [ "$t_ok" = "True" ] && [ -n "$t_last" ]; then
      echo "связь с Telegram: ok (последний ответ $(fmt_age $((now - t_last))))"
    elif [ "$t_ok" = "False" ]; then
      echo "связь с Telegram: НЕТ — $t_err"
      echo "                  (бот продолжает работать и переспрашивать, это не поломка)"
    else
      echo "связь с Telegram: ещё не проверялась"
    fi
  fi
fi

# --- накопленное ---
DB="$DIR/data/logger.db"
if [ -f "$DB" ]; then
  stat=$(docker exec "$CONTAINER" python -c "
import sqlite3
db = sqlite3.connect('/data/logger.db')
n = db.execute('select count(*) from messages').fetchone()[0]
last = db.execute('select max(date) from messages').fetchone()[0]
print(n); print(last or '')" 2>/dev/null)
  cnt=$(echo "$stat" | sed -n 1p)
  last=$(echo "$stat" | sed -n 2p)
  files=$(ls -1 "$DIR/data/media" 2>/dev/null | wc -l | tr -d ' ')
  echo "записей в базе:   ${cnt:-?} | файлов на диске: $files"
  [ -n "$last" ] && echo "последнее сообщение: $last"
fi

# --- контейнер ---
st=$(docker inspect "$CONTAINER" --format '{{.State.Status}}{{if .State.Health}} ({{.State.Health.Status}}){{end}}, перезапусков {{.RestartCount}}' 2>/dev/null)
echo "контейнер:        ${st:-не найден}"

exit $rc
