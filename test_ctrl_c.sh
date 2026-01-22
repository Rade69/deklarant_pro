#!/bin/bash
# Test script za proveru Ctrl+C funkcionalnosti

echo "Pokrećem aplikaciju i šaljem SIGINT nakon 1 sekunde..."
python3 __main__.py &
PID=$!

sleep 1
echo "Šaljem SIGINT (Ctrl+C) na proces $PID..."
kill -SIGINT $PID

sleep 0.5
if kill -0 $PID 2>/dev/null; then
    echo "✗ Proces još uvek radi, moram ga ubiti sa SIGKILL"
    kill -9 $PID
    exit 1
else
    echo "✓ Proces se uspešno zaustavio sa SIGINT (Ctrl+C)"
    exit 0
fi
