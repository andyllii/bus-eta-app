#!/usr/bin/env bash
UA="transportation-api/0.2"
for r in 6 7 71 780 M47 12 25 90 970; do
  curl -s -A "$UA" "https://rt.data.gov.hk/v2/transport/citybus/eta/CTB/$r/001027" -o /tmp/c.json
  n=$(python3 -c "import json;print(len(json.load(open('/tmp/c.json')).get('data') or []))" 2>/dev/null)
  echo "route $r -> $n etas"
done
