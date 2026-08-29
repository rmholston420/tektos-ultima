#!/bin/bash
# Safe llama-server restart with 20-second warning
# This script:
#   1. Reloads systemd config
#   2. Waits 20 seconds (gives you time to cancel)
#   3. Restarts the server
#   4. Waits for it to be healthy on port 8090
#
# If the new model fails to load, run:
#   /home/rmholston/dev/tektos-ultima-v1/scripts/rollback_llama_server.sh

set -e

echo "=== llama-server restart to Qwen3.8-27B ==="
echo "WARNING: This will restart your LLM server in 20 seconds."
echo "If you want to cancel, press Ctrl+C now."
echo ""

# Countdown with visible timer
for i in 20 19 18 17 16 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1; do
    echo -ne "\rWaiting $i seconds... (Ctrl+C to cancel)  "
    sleep 1
done
echo ""

# Reload systemd and restart
systemctl --user daemon-reload
systemctl --user restart llama-server-8090

echo "Server restarting... waiting for health check on port 8090"

# Wait for server to be healthy (up to 60 seconds)
for i in $(seq 1 60); do
    if curl -s http://127.0.0.1:8090/v1/models > /dev/null 2>&1; then
        echo "✅ Server is healthy on port 8090"
        
        # Print model info
        MODEL_INFO=$(curl -s http://127.0.0.1:8090/v1/models | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('data', []):
    print(f\"Model ID: {m['id']}\")
    print(f\"Object: {m.get('object', 'N/A')}\")
" 2>/dev/null || echo "Could not parse model info")
        echo "$MODEL_INFO"
        
        echo ""
        echo "=== Restart complete ==="
        echo "Your llama-server is now running Qwen3.8-27B-Q4_K_M with:"
        echo "  - MTP speculative decoding (n-max=3) for ~1.7x speedup"
        echo "  - 131K context window"
        echo "  - reasoning off, temp=0.1, top-k=40"
        echo ""
        echo "If something goes wrong, run:"
        echo "  /home/rmholston/dev/tektos-ultima-v1/scripts/rollback_llama_server.sh"
        exit 0
    fi
    echo -ne "\rWaiting for server... ($i/60)  "
    sleep 1
done

echo ""
echo "❌ Server did not become healthy within 60 seconds."
echo "Run the rollback script to restore Qwen3.6-35B-A3B:"
echo "  /home/rmholston/dev/tektos-ultima-v1/scripts/rollback_llama_server.sh"
exit 1
