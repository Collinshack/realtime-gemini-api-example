
import asyncio
import base64
import json
import os
import pyaudio
from websockets.client import connect


class SimpleGeminiVoice:
    def __init__(self):
        self.audio_queue = asyncio.Queue()
        self.api_key = "ADD_YOUR_API_KEY"
        self.model = "gemini-2.0-flash-exp"
        self.uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={self.api_key}"
        # Audio settings
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.CHUNK = 512
        self.RATE = 16000

    async def start(self):
        # Initialize websocket
        self.ws = await connect(
            self.uri,
            extra_headers={"Content-Type": "application/json"}
        )
        # Setup message with system instruction based on the documentation
        setup_message = {
            "setup": {
                "model": f"models/{self.model}",
                "system_instruction": {
                    "parts": [
                        {
                            "text": "You are a specialized web development assistant. Only answer questions related to web development, programming, coding, frameworks, databases, and related technical topics. For any questions outside the domain of web development, politely explain that you are focused on helping with web development questions only. Your expertise includes HTML, CSS, JavaScript, popular frameworks like React, Vue, Angular, backend technologies like Node.js, Python/Django, Ruby on Rails, databases, web security, performance optimization, and modern web development practices."
                        }
                    ]
                }
            }
        }
        
        await self.ws.send(json.dumps(setup_message))
        await self.ws.recv()
        print("Connected to Gemini, You can start talking now")
        print("Ask web development questions only - this assistant is specialized in web dev topics")
        
        # Start audio streaming
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.capture_audio())
            tg.create_task(self.stream_audio())
            tg.create_task(self.play_response())

    async def capture_audio(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        # Remove the system prompt code as it's now in the setup
        while True:
            data = await asyncio.to_thread(stream.read, self.CHUNK)
            await self.ws.send(
                json.dumps(
                    {
                        "realtime_input": {
                            "media_chunks": [
                                {
                                    "data": base64.b64encode(data).decode(),
                                    "mime_type": "audio/pcm",
                                }
                            ]
                        }
                    }
                )
            )

    async def stream_audio(self):
        async for msg in self.ws:
            response = json.loads(msg)
            try:
                audio_data = response["serverContent"]["modelTurn"]["parts"][0][
                    "inlineData"
                ]["data"]
                self.audio_queue.put_nowait(base64.b64decode(audio_data))
            except KeyError:
                pass
            try:
                turn_complete = response["serverContent"]["turnComplete"]
            except KeyError:
                pass
            else:
                if turn_complete:
                    # If you interrupt the model, it sends an end_of_turn. For interruptions to work, we need to empty out the audio queue
                    print("\nEnd of turn")
                    while not self.audio_queue.empty():
                        self.audio_queue.get_nowait()

    async def play_response(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT, channels=self.CHANNELS, rate=24000, output=True
        )
        while True:
            data = await self.audio_queue.get()
            await asyncio.to_thread(stream.write, data)


if __name__ == "__main__":
    client = SimpleGeminiVoice()
    asyncio.run(client.start())
