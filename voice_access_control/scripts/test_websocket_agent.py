import asyncio
import websockets
import json
import numpy as np
import argparse
import wave
import sys

async def send_audio(uri, audio_file=None):
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        
        # 1. Prepare Audio Data
        if audio_file:
            print(f"Reading audio from {audio_file}...")
            wf = wave.open(audio_file, 'rb')
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                print("Warning: Audio file must be Mono, 16-bit, 16kHz PCM wav.")
            
            chunk_size = 480  # 30ms at 16kHz
            data = wf.readframes(chunk_size)
            
            while len(data) > 0:
                await websocket.send(data)
                data = wf.readframes(chunk_size)
                # Simulate real-time streaming
                await asyncio.sleep(0.03) 
            
            wf.close()
            print("Finished sending file.")
        else:
            print("Generating synthetic speech-like audio (modulated noise)...")
            # Generate 3 seconds of modulated white noise to trigger VAD
            sample_rate = 16000
            duration = 3.0
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            
            # 1. White noise carrier
            carrier = np.random.normal(0, 0.1, len(t))
            
            # 2. Syllabic modulation (2-5Hz)
            modulator = 0.5 * (1 + np.sin(2 * np.pi * 3 * t))
            
            # 3. Apply envelope
            audio_data = (carrier * modulator * 32767).astype(np.int16)
            
            chunk_size = 480 # 30ms
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size].tobytes()
                await websocket.send(chunk)
                await asyncio.sleep(0.03)
            
            print("Finished sending synthetic audio.")

        # Keep connection open for a bit to receive responses
        print("Waiting for responses (timeout=10s)...")
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                print(f"\nReceived: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                if data.get("type") == "result" and data.get("agent"):
                    print("Agent responded! Test finished.")
                    # break # Uncomment to exit after first agent response
        except asyncio.TimeoutError:
            print("No more responses (timeout).")
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Voice Access Control WebSocket")
    parser.add_argument("--uri", default="ws://localhost:9000/ws/audio", help="WebSocket URI")
    parser.add_argument("--file", help="Path to a 16kHz mono wav file")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(send_audio(args.uri, args.file))
    except KeyboardInterrupt:
        print("\nTest stopped.")
    except Exception as e:
        print(f"\nError: {e}")
