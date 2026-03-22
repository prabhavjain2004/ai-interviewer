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
        
        # Turn 1: Greeting
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="Hello! Please ask me a question.")],
            ),
            turn_complete=True,
        )
        print("Turn 1 sent...")
        
        async for resp in session.receive():
            if resp.data:
                print(f"Turn 1 audio bytes: {len(resp.data)}")
            if resp.server_content is not None and resp.server_content.turn_complete:
                print("Turn 1 audio finished playing.")
                break
                
        # Turn 2: User responds
        await session.send_realtime_input(
            audio=types.Blob(
                data=b'\x00' * 32000,
                mime_type="audio/pcm;rate=16000",
            )
        )
        print("Turn 2: user audio sent...")
        
        # Signal Activity End
        await session.send_realtime_input(activity_end=types.ActivityEnd())
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="")],
            ),
            turn_complete=True,
        )
        print("Turn 2: Activity end & client content sent. Waiting...")
        
        async for resp in session.receive():
            print("Turn 2 resp:", resp)
            if resp.data:
                print(f"Received audio bytes: {len(resp.data)}")
            if resp.server_content is not None and resp.server_content.turn_complete:
                print("Turn 2 complete received!")
                break

asyncio.run(main())
