#!/usr/bin/env python3
"""Test vision models by analyzing a screenshot"""
import subprocess
import json
import time
import sys

MODELS = {
    "3B": {
        "path": "/home/rmholston/dev/openhands-ext-v1/models/qwen2.5-vl-3b-gguf/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        "mmproj": "/home/rmholston/dev/openhands-ext-vl-3b-gguf/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        "port": 8083,
    },
    "7B": {
        "path": "/home/rmholston/dev/openhands-ext-v1/models/qwen2.5-vl-7b-gguf/Qwen2.5-VL-7B-Instruct-abliterated.IQ4_XS.gguf",
        "mmproj": "/home/rmholston/dev/openhands-ext-vl-7b-gguf/Qwen2.5-VL-7B-Instruct-abliterated.mmproj-Q8_0.gguf",
        "port": 8084,
    },
    "32B": {
        "path": "/home/rmholston/dev/openhands-ext-v1/models/qwen2.5-vl-32b-gguf/Qwen2.5-VL-32B-Instruct-iq1_s.gguf",
        "mmproj": "/home/rmholston/dev/openhands-ext-vl-32b-gguf/Qwen2.5-VL-32B-Instruct-mmproj-f16.gguf",
        "port": 8085,
    },
}


def start_vision_server(model_name, config):
    """Start llama.cpp server for a vision model"""
    print(f"\n{'='*60}")
    print(f"Starting vision server for {model_name}")
    print(f"Model: {config['path']}")
    print(f"mmproj: {config['mmproj']}")
    print(f"Port: {config['port']}")
    print("="*60)

    # Check files exist
    for f in [config["path"], config["mmproj"]]:
        if not subprocess.run(["test", "-f", f]).returncode == 0:
            print(f"ERROR: File not found: {f}")
            return None

    # Start server
    cmd = [
        "llama-server",
        "--model", config["path"],
        "--mmproj", config["mmproj"],
        "--host", "127.0.0.1",
        "--port", str(config["port"]),
        "-ngl", "99",  # Offload all layers to GPU
        "--ctx-size", "4096",  # Small context for image + text
        "--threads", "8",
        "--batch-size", "16",
    ]
    print(f"Command: {' '.join(cmd)}")

    import subprocess
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for server to start
    time.sleep(5)
    return process


async def test_vision(model_name, config):
    """Test vision model with a screenshot"""
    # First, take a screenshot
    print(f"\nTaking screenshot...")
    screenshot_path = f"/tmp/vision-test-{model_name}.png"

    # Use display to capture (since we're in a Wayland session)
    result = subprocess.run(
        ["import", "-window", "root", screenshot_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Try scrot as fallback
        result = subprocess.run(
            ["scrot", screenshot_path],
            capture_output=True, text=True
        )
    if result.returncode != 0:
        print(f"Failed to take screenshot: {result.stderr}")
        return

    print(f"Screenshot saved: {screenshot_path}")

    # Start the vision server
    process = start_vision_server(model_name, config)
    if not process:
        return

    try:
        # Wait for server to be ready
        print(f"Waiting for {model_name} server to start...")
        time.sleep(10)

        # Test with a simple prompt
        print(f"Testing {model_name}...")
        import urllib.request
        import base64

        # Read screenshot
        with open(screenshot_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        # Prepare the API call
        prompt = "Describe what you see in this screenshot in detail."
        messages = [
            {"role": "user", "content": [
                {"type": "image", "image": f"data:image/png;base64,{img_data}"},
                {"type": "text", "text": prompt},
            ]},
        ]

        payload = {
            "model": config["path"].split("/")[-1],
            "messages": messages,
            "max_tokens": 1000,
            "stream": False,
        }

        # Call the API
        url = f"http://127.0.0.1:{config['port']}/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )

        print(f"Calling {url}...")
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())

        # Print the response
        print(f"\n{model_name} Response:")
        print("="*60)
        print(result["choices"][0]["message"]["content"])
        print("="*60)

        # Print usage stats
        if "usage" in result:
            print(f"\nUsage: {json.dumps(result['usage'], indent=2)}")

    except Exception as e:
        print(f"Error testing {model_name}: {e}")
    finally:
        # Stop the server
        process.terminate()
        process.wait()
        print(f"\n{model_name} server stopped")


def main():
    """Test all vision models"""
    # Test the 3B model first (fastest, fits on GPU)
    test_vision("3B", MODELS["3B"])

    # Test the 7B model
    test_vision("7B", MODELS["7B"])

    # Test the 32B model
    test_vision("32B", MODELS["32B"])


if __name__ == "__main__":
    main()
