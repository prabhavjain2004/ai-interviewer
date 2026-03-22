import asyncio
import os
from google import genai
from google.genai import types

os.environ["GEMINI_API_KEY"] = "AIzaSyBOwnYjaVCpmfmWFHu31pwcn0j55urth5c"

async def main():
    client = genai.Client()
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True,
            )
        ),
    )
    async with client.aio.live.connect(model="models/gemini-2.5-flash-native-audio-latest", config=config) as session:
        print("Connected.")
        
        try:
            print("Sending dummy audio...")
            await session.send_realtime_input(
                audio=types.Blob(
                    data=b'\x00' * 8000,
                    mime_type="audio/pcm;rate=16000",
                )
            )
            print("Sending activity end...")
            await session.send_realtime_input(activity_end=types.ActivityEnd())
            print("Activity end sent. Waiting for response...")
            
            async for resp in session.receive():
                print("Received:", resp)
                if resp.server_content is not None and resp.server_content.turn_complete:
                    break
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(main())
