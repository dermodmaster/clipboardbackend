from tinydb import TinyDB, Query, where
import time
from enum import Enum
import websockets
import asyncio
import json

db = TinyDB('database.json')
videos = db.table('videos')
WEBSOCKETS = set()
Viewer = []
Controller = []
Playing = []
video = None



async def createVideo(title, begin, duration, link):
    videos.insert({"title": title, "begin": begin, "duration": duration, "link": link, "ts": time.time()})
    await notify_videos()

async def deleteVideo(timestamp):
    videos.remove(where('ts') == timestamp)
    await notify_videos()

def users_event():
    return json.dumps({"type": "users", "count": len(WEBSOCKETS), "viewer": len(Viewer), "controller": len(Controller)})

def status_event():
    return json.dumps({
        "type":"status", "playing": len(Playing), "video": video
    })

def stop_video():
    return json.dumps({
        "type": "stopVideo"
    })

async def stopVideo():
    if WEBSOCKETS:
        message = stop_video()
        await asyncio.wait([user.send(message) for user in Viewer])

async def playingStatus():
    if WEBSOCKETS:
        message = status_event()
        await asyncio.wait([user.send(message) for user in Controller])

def video_event():
    return json.dumps({"type": "videos", "videos": videos.all()})

def play_video_event(title, begin, duration, link):
    global video
    video = {"title": title, "begin": begin, "duration": duration, "link": link}
    return json.dumps({"type": "playVideo", "title": title, "begin": begin, "duration": duration, "link": link})

async def play_video(title, begin, duration, link):
    if WEBSOCKETS:
        message = play_video_event(title, begin, duration, link)
        await asyncio.wait([user.send(message) for user in Viewer])

async def notify_users():
    if WEBSOCKETS:  # asyncio.wait doesn't accept an empty list
        message = users_event()
        await asyncio.wait([user.send(message) for user in WEBSOCKETS])


async def notify_videos():
    if WEBSOCKETS:  # asyncio.wait doesn't accept an empty list
        message = video_event()
        await asyncio.wait([user.send(message) for user in WEBSOCKETS])


async def register(websocket):
    WEBSOCKETS.add(websocket)
    await notify_users()


async def softUnregister(websocket):
    if websocket in Controller:
        Controller.remove(websocket)
    if websocket in Viewer:
        Viewer.remove(websocket)
    if websocket in Playing:
        Viewer.remove(websocket)


async def unregister(websocket):
    WEBSOCKETS.remove(websocket)
    await softUnregister(websocket)
    await notify_users()


async def handle(websocket, path):
    # register(websocket) sends user_event() to websocket
    await register(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            print(data)
            if "status" in data.keys():
                if data["status"] == "playing":
                    if websocket not in Playing:
                        Playing.append(websocket)
                    await playingStatus()
                if data["status"] == "finished":
                    Playing.remove(websocket)
                    await playingStatus()
            if "action" in data.keys():
                if data["action"] == "registerViewer":
                    if websocket in Controller:
                        Controller.remove(websocket)
                    Viewer.append(websocket)
                    await notify_users()
                if data["action"] == "registerController":
                    if websocket in Viewer:
                        Viewer.remove(websocket)
                    Controller.append(websocket)
                    await notify_users()
                if data["action"] == "unregister":
                    await softUnregister(websocket)
                    await notify_users()
                if data["action"] == "getVideos":
                    message = video_event()
                    await websocket.send(message)
                if data["action"] == "createVideo":
                    await createVideo(data["title"], data["begin"], data["duration"], data["link"])
                if data["action"] == "deleteVideo":
                    await deleteVideo(data["ts"])
                if data["action"] == "playVideo":
                    await play_video(data["title"], data["begin"], data["duration"], data["link"])
                if data["action"] == "stopVideo":
                    await stopVideo()

            # await notify_state()
    finally:
        await unregister(websocket)


start_server = websockets.serve(handle, "0.0.0.0", 6789)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
