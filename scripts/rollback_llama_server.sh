#!/bin/bash
# Rollback llama-server to Qwen3.6-35B-A3B (original model)
# Use this if Qwen3.8-27B fails to load or causes issues

set -e

echo "=== Rolling back llama-server to Qwen3.6-35B-A3B ==="

# Restore the original model path and settings
cat > /home/rmholston/.config/systemd/user/llama-server-8090.service << 'EOF'
[Unit]
Description=Llama.cpp Server — Qwen3.6-35B-A3B (port 8090, primary)
After=network.target

[Service]
Type=simple
ExecStart=/home/rmholston/llama.cpp/build/bin/llama-server \
  --model /home/rmholston/dev/openhands-ext-v1/models/qwen3_6-35b-a3b-bartowski-q5_k_m-gguf/Qwen_Qwen3.6-35B-A3B-Q5_K_M.gguf \
  --host 127.0.0.1 --port 8090 \
  -ngl 999 \
  --ctx-size 262144 \
  -b 8192 --ubatch-size 2048 \
  --flash-attn on \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --cache-ram -1 \
  --parallel 1 \
  -t 12 \
  --jinja \
  --chat-template-file /home/rmholston/qwen-templates/chat_template.jinja \
  --reasoning off \
  --cache-reuse 512 \
  --n-predict 16384 \
  --metrics \
  --no-context-shift \
  --cont-batching \
  --temp 0.1 \
  --top-p 0.95 \
  --top-k 40 \
  --min-p 0.02 \
  --presence-penalty 0.1 \
  --repeat-penalty 1.05 \
  --frequency-penalty 0.0 \
  --seed 7 \
  --cache-prompt
Environment=CUDA_VISIBLE_DEVICES=0
Restart=always
RestartSec=5
SuccessExitStatus=143
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user restart llama-server-8090

echo "Rolling back... waiting for health check on port 8090"

for i in $(seq 1 60); do
    if curl -s http://127.0.0.1:8090/v1/models > /dev/null 2>&1; then
        echo "✅ Rollback complete — Qwen3.6-35B-A3B is running on port 8090"
        exit 0
    fi
    sleep 1
done

echo "❌ Server did not become healthy within 60 seconds."
exit 1
