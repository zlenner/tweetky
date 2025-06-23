import asyncio
import base64
import datetime
from io import BytesIO
import json
import os
import re
import time
import traceback
import timeago
from twikit import Client, Tweet
import aiohttp
from dotenv import load_dotenv
import numpy as np
import os
import requests
import twikit
import twikit.media
import builtins
from contextlib import contextmanager
import random

load_dotenv()

CHANNEL_ID=os.getenv("CHANNEL_ID", "")
X_USERNAME=os.getenv("X_USERNAME", "")
X_EMAIL=os.getenv("X_EMAIL", "")
X_PASSWORD=os.getenv("X_PASSWORD", "")
X_COOKIES=os.getenv("X_COOKIES", None)
X_FORCE_PUSH_AUTH=os.getenv("X_FORCE_PUSH_AUTH", None)
WHATSAPP_BASIC_AUTH=os.getenv("WHATSAPP_BASIC_AUTH", "")

WHATSAPP_HEADERS = {
    "Authorization": f"Basic {base64.b64encode(WHATSAPP_BASIC_AUTH.encode()).decode()}"
}

DATA_DIR = "./data/"

WHATSAPP_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3000")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Created {DATA_DIR}")
else:
    print(DATA_DIR + " exists.")
    for file in os.listdir(DATA_DIR):
        print("->", file)

print("Verifying WARP is working...")

WARP_PROXY_URL = os.getenv("WARP_PROXY_URL")

assert WARP_PROXY_URL, "WARP_PROXY_URL env variable must be defined."

response = requests.get('https://ifconfig.me/')
print(f"Your IP address: {response.text.strip()}")

while True:
    try:
        response = requests.get('https://ifconfig.me/', proxies={'http': WARP_PROXY_URL, 'https': WARP_PROXY_URL})
        print(f"Your IP through proxy: {response.text.strip()}")
        break
    except requests.exceptions.ConnectionError as e:
        if "[Errno 111] Connection refused" in str(e):
            print("WARP Proxy not yet started...")
            time.sleep(2)
            continue
        else:
            raise e

print("Verifying WhatsApp is logged in...", '/app/login')
while True:
    try:
        response = requests.get(f'{WHATSAPP_URL}/app/login', headers=WHATSAPP_HEADERS)
        if response.status_code == 401:
            raise Exception(f"WhatsApp API returned status code {response.status_code}: {response.text}")
        
        data = response.json()
        
        if data.get("code") == "SUCCESS" and data.get("results", {}).get("qr_link"):
            raise Exception(f"Login to WhatsApp @ {data.get('results', {}).get('qr_link')}")
        elif data.get("code") == "ALREADY_LOGGED_IN":
            print("WhatsApp is logged in!")
            break
        elif data.get("code") == "SESSION_SAVED_ERROR":
            print("WhatsApp session already saved, proceeding with the script.")
            print("Retrying in 2 seconds...")
            time.sleep(2)
            continue
        else:
            raise Exception(f"WhatsApp API returned unexpected response: {data}")

    except Exception as e:
        print(f"WhatsApp API authentication failed.")
        raise e

if (X_USERNAME == "" or X_PASSWORD == "" or X_EMAIL == "") and not X_COOKIES:
    raise Exception("Either one of\n1. X_USERNAME, X_PASSWORD\nX_EMAIL 2. X_COOKIES.\n must be provided.")
else:
    print("Credentials provided, proceeding with the script.")

class PersistentJsonData:
    def __init__(self, filename, default_data):
        self.filename = filename

        try:
            with open(DATA_DIR + self.filename, 'r') as f:
                self.data = json.load(f)

        except FileNotFoundError:
            self.data = default_data
    
    def _overwrite_and_save(self, new_data):
        self.data = new_data
        self.save_to_file()

    def save_to_file(self):
        with open(DATA_DIR + self.filename, 'w+') as f:
            json.dump(self.data, f)

class PersistentSet(PersistentJsonData):
    def __init__(self, filename):
        super().__init__(filename, [])
        
        print(f"Initialized PersistentSet with {len(self.data)} items.")

    async def add(self, tweet: Tweet):
        self.data.append(tweet.id)
        self.save_to_file()

    async def remove(self, tweet: Tweet):
        self.data.remove(tweet.id)
        self.save_to_file()

    def exists(self, tweet: Tweet):
        return tweet.id in self.data

    def save_to_file(self):
        with open(DATA_DIR + self.filename, 'w+') as f:
            json.dump(self.data, f)

class SentTweets(PersistentSet):
    def __init__(self, filename="sent_tweets.json"):
        super().__init__(filename)
        self.errored = PersistentSet("errored_tweets.json")

    async def add(self, tweet: Tweet):
        try:
            await self.__send_request_to_post_video(tweet)

            self.data.append(tweet.id)
            self.save_to_file()
            
        except Exception as e:
            await self.errored.add(tweet)

            print("Failed to send request to post message to WhatsApp.", e)
            traceback.print_exc()

    async def __send_request_to_post_video(self, tweet: Tweet):
        async with aiohttp.ClientSession() as session:
            # Post to WhatsApp
            session.headers.update(WHATSAPP_HEADERS)

            tweet_text: str = build_tweet_text(tweet)
            tweet_medias = [] if not tweet.media else list(map(build_tweet_media, tweet.media))

            async def send_media_photo(media, caption: str = ""):
                async with session.post(f'{WHATSAPP_URL}/send/image', json={
                    "image_url": media["url"],
                    "phone": CHANNEL_ID,
                    "caption": caption
                }) as response:
                    res = await response.json()
                    if res["code"] != "SUCCESS":
                        print("Failed to send photo to WhatsApp API.")
                        print(res)
                        raise Exception("Failed to send photo to WhatsApp API.")
                    else:
                        print("Sent photo to WhatsApp API.")
            
            async def send_media_video(media, caption = ""):
                video_url = media["video"]["url"]

                # Stream video directly from URL
                async with session.get(video_url) as video_response:
                    video_bytes = await video_response.read()

                    form = aiohttp.FormData()
                    form.add_field("phone", CHANNEL_ID)
                    form.add_field("video", BytesIO(video_bytes),
                                filename="video.mp4",
                                content_type="video/mp4")
                    form.add_field("compress", "true")
                    if caption != "":
                        form.add_field("caption", caption)

                    async with session.post(f"{WHATSAPP_URL}/send/video", data=form) as response:
                        res = await response.json()
                        if res["code"] != "SUCCESS":
                            print("Failed to send video to WhatsApp API.")
                            print(res)
                            raise Exception("Failed to send video to WhatsApp API.")
                        else:
                            print(res)
                            print("Sent video to WhatsApp API.")

            async def send_text_message(tweet_text: str):
                # Send message to WhatsApp API
                async with session.post(f'{WHATSAPP_URL}/send/message', json={
                    "message": tweet_text,
                    "phone": CHANNEL_ID,
                }) as response:
                    res = await response.json()
                    if res["code"] != "SUCCESS":
                        print("Failed to send message to WhatsApp API.")
                        print(res)
                        raise Exception("Failed to send message to WhatsApp API.")
                    else:
                        print("Sent message to WhatsApp API.")

            if len(tweet_medias) == 0:
                print("No media found in tweet, sending text message...")
                await send_text_message(tweet_text)
            elif len(tweet_medias) == 1:
                first_media = tweet_medias[0]
                if first_media["type"] == "photo":
                    print("Sending single photo...")
                    await send_media_photo(first_media, tweet_text)
                else:
                    print("Sending single video...")
                    await send_media_video(first_media, tweet_text)
            else:
                first_media = tweet_medias[0]
                if first_media["type"] == "photo":
                    print("Sending first photo...")
                    await send_media_photo(first_media, tweet_text  + "\n\n*More photos/videos from tweet below...*")
                else:
                    print("Sending first video...")
                    await send_media_video(first_media, tweet_text  + "\n\n*More photos/videos from tweet below...*")

                for media in tweet_medias[1:]:
                    print("Sending media...")
                    if media["type"] == "photo":
                        await send_media_photo(media)
                    else:
                        await send_media_video(media)

sent_tweets = SentTweets()
x_auth_errors = PersistentJsonData("x_auth_status.json", {})

import numpy as np

def generate_time_interval(low: float, high: float):
    """
    Generate a random time interval between `low` and `high` seconds
    with a normal distribution centered in the range,
    and random decimal component.

    Parameters:
    - low (float): minimum interval value
    - high (float): maximum interval value

    Returns:
    - float: generated time interval
    """
    if low >= high:
        raise ValueError("Low bound must be less than high bound")

    # Mean in the middle of the range
    mean = (low + high) / 2

    # Scale to fit most values within [low, high] (approx 95% of values within 2 std devs)
    scale = (high - low) / 4

    # Generate normally distributed value
    interval = np.random.normal(loc=mean, scale=scale)
    
    # Clamp to [low, high]
    interval = np.clip(interval, low, high)
    
    # Get integer part and add a new random decimal
    integer_part = int(interval)
    random_decimal = np.random.random()
    final_interval = integer_part + random_decimal

    # Final clamp to ensure within range
    return np.clip(final_interval, low, high)

def build_tweet_media(media: twikit.tweet.MEDIA_TYPE):
    """
    Process media object and return structured media data
    """
    if isinstance(media, twikit.media.Video):
        # Filter variants to only include MP4 videos
        variants = [
            variant for variant in media.video_info["variants"] 
            if variant["content_type"] == "video/mp4"
        ]
        
        # Find the variant with the highest bitrate
        bitrates = [variant.get("bitrate", 0) for variant in variants]
        best_bitrate = max(bitrates)
        best_variant = next(
            (variant for variant in variants if variant.get("bitrate") == best_bitrate), 
            None
        )
        
        if not best_variant:
            raise Exception("Couldn't find best variant for video.")
        
        generator = {
            "type": "video",
            "poster": media.media_url,
            "size": {
                "height": media.sizes["large"]["h"],
                "width": media.sizes["large"]["w"],
            },
            "video": {
                "bitrate": best_variant.get("bitrate"),
                "url": best_variant["url"],
                "duration_millis": media.video_info.get("duration_millis"),
            }
        }
        
        return generator
        
    elif isinstance(media, twikit.media.Photo):
        generator = {
            "type": "photo",
            "url": media.media_url,
            "size": {
                "height": media.sizes["large"]["h"],
                "width": media.sizes["large"]["w"],
            }
        }
        return generator
        
    else:  # animated_gif
        return {
            "type": "animated_gif",
            "poster": media.media_url,
            "size": {
                "height": media.sizes["large"]["h"],
                "width": media.sizes["large"]["w"],
            },
            "video": {
                "bitrate": media.video_info["variants"][0].get("bitrate"),
                "url": media.video_info["variants"][0]["url"],
                "duration_millis": 6000,
            }
        }

def build_tweet_text(tweet: Tweet) -> str:
    tweet_url = f"https://x.com/{tweet.user.screen_name}/status/{tweet.id}"

    tweet_text: str = tweet.full_text
    if tweet.media:
        for media in tweet.media:
            tweet_text = tweet_text.replace(media.url, "")

    tweet_text = tweet_text.strip()
    tweet_text += "\n\n" + tweet_url

    time = datetime.datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
    tweet_text += "\n\n" + time.strftime("%I:%M%p %Z, %B %d")

    return f"_*@{tweet.user.screen_name} {'✓' if tweet.user.is_blue_verified else ''}:*_\n\n" + tweet_text

client = Client('en-US',
    user_agent=os.getenv("X_USER_AGENT", "Mozilla/5.0 (Linux; Android 16; SM-N960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.90 Mobile Safari/537.36"),
    proxy=WARP_PROXY_URL
)

@contextmanager
def intercept_twitter_flows():
    _print = builtins.print
    _input = builtins.input

    time_of_call = datetime.datetime.now()
    
    printed_text = ""
    
    def intercepted_print(*args, **kwargs):
        nonlocal printed_text
        printed_text += " ".join(str(arg) for arg in args) + "\n"
        _print(*args, **kwargs)
    
    def intercepted_input(prompt=""):
        nonlocal printed_text
        printed_text += prompt

        if "Verify your identity by entering the email address" in printed_text:
            print(printed_text)
            
            sleep_time = round(generate_time_interval(2, 6), 2)
            print(f"Naturally sleeping for {sleep_time}...")
            time.sleep(sleep_time)
            
            return X_EMAIL
        elif "code sent":
            IMPROV_MX_API_KEY = os.getenv("IMPROVMX_APIKEY", None)
            if IMPROV_MX_API_KEY is not None:
                print("Fetching verification code from ImprovMX logs...")
                matching_logs = []
                while len(matching_logs) == 0:
                    response = requests.get("https://api.improvmx.com/v3/domains/obaid.xyz/logs", headers={
                        "Authorization": f"Basic api:{IMPROV_MX_API_KEY}"
                    })
                    logs = response.json()
                    matching_logs = [log for log in logs['logs'] if log['created'] > time_of_call and 'Your X confirmation code is' in log['subject']]
                    print("No verification code email found...")
                    time.sleep(2)
                
                match = re.search(r'(?<=Your X confirmation code is )[a-z0-9]+', matching_logs[0]["subject"])
                verification_code = match.group() if match else None

                sleep_time = round(generate_time_interval(2, 6), 2)
                print(f"Naturally sleeping for {sleep_time}...")
                time.sleep(sleep_time)

                return verification_code
            else:
                print("No ImprovMX API Key provided, exiting application.")
                raise twikit.errors.Unauthorized("Code requested... no API key provided to pull from ImprovMX automatically.")
        else:
            print("Unknown input requested...")
            _input(prompt)
    
    builtins.print = _print
    builtins.input = _input
    
    try:
        yield
    finally:
        builtins.print = intercepted_print
        builtins.input = intercepted_input

async def login_client():
    print("Logging in to X...", dict(
        X_USERNAME=X_USERNAME,
        X_EMAIL=X_EMAIL,
        X_PASSWORD=X_PASSWORD,
        X_USER_AGENT=os.getenv("X_USER_AGENT")
    ))
    with intercept_twitter_flows():
        await client.login(
            auth_info_1=X_USERNAME ,
            auth_info_2=X_EMAIL,
            password=X_PASSWORD,
        )

    client.save_cookies(DATA_DIR + 'cookies.json')

async def attempt_cached_login():
    if X_COOKIES is not None:
        cookies = json.loads(base64.b64decode(os.getenv("X_COOKIES", "{}")).decode())
        client.set_cookies(cookies)
        print("Successfully loaded cookies from environment variable.")
    else:
        try:
            with open(DATA_DIR + 'cookies.json', 'r') as f:
                cookies = json.load(f)
                client.set_cookies(cookies)
                print("Successfully loaded cookies.")
                print("X_COOKIES=" + base64.b64encode(json.dumps(cookies).encode()).decode())
        except FileNotFoundError:
            try:
                await login_client()
                print("Successfully logged in and saved cookies.")
            except twikit.TwitterException as e:
                x_auth_errors._overwrite_and_save({
                    "error": True,
                    "message": str(e),
                    "args": e.args,
                    "X_COOKIES": X_COOKIES,
                    "X_USERNAME": X_USERNAME,
                    "X_EMAIL": X_EMAIL,
                    "X_PASSWORD": X_PASSWORD,
                    "X_FORCE_PUSH_AUTH": X_FORCE_PUSH_AUTH
                })
                raise e

def pull_straw(probability: float) -> bool:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0 and 1.")
    
    return random.random() < probability

tweets_fetched_per_day = PersistentJsonData("tweets_fetched_per_day.json", {})

async def main():
    if x_auth_errors.data.get("error"):
        if X_COOKIES and X_COOKIES == x_auth_errors.data.get("X_COOKIES"):
            raise Exception('X threw an error last time it was run, remove or change X_COOKIES and restart service.')
        elif os.path.exists(DATA_DIR + 'cookies.json'):
            os.remove(DATA_DIR + 'cookies.json')
            raise Exception('X threw an error last time it was run, deleting saved cookies...')
        elif (X_USERNAME == x_auth_errors.data.get("X_USERNAME")) and (X_PASSWORD == x_auth_errors.data.get("X_PASSWORD")) and (X_EMAIL == x_auth_errors.data.get("X_EMAIL")):
            if X_FORCE_PUSH_AUTH == x_auth_errors.data.get("X_FORCE_PUSH_AUTH"):
                raise Exception('X threw an error last time it was run with these USERNAME+EMAIL+PASSWORD credentials, try setting X_COOKIES or sign in manually once and change the value of X_FORCE_PUSH_AUTH (to anything else) to remove this flag...')
            else:
                print("X_FORCE_PUSH_AUTH triggered, removing auth error and continuing application...")
                x_auth_errors.data["X_FORCE_PUSH_AUTH"] = X_FORCE_PUSH_AUTH
                x_auth_errors.save_to_file()
        else:
            print("X Credentials changed, removing auth error and continuing application...")
            x_auth_errors.data = {}
            x_auth_errors.save_to_file()
    
    await attempt_cached_login()

    user_handles = [handle for handle in os.getenv("X_HANDLES_TO_WATCH", "DropSiteNews").split(",") if handle.strip()]

    try:
        while True:
            latest_day_start = 0 if not len(tweets_fetched_per_day.data.keys()) else max(map(int, tweets_fetched_per_day.data.keys()))
            now_utc = datetime.datetime.now(datetime.timezone.utc)

            if int((now_utc - datetime.timedelta(days=1)).timestamp()) > int(latest_day_start):
                tweets_fetched_per_day.data[int(now_utc.timestamp())] = 0
                tweets_fetched_per_day.save_to_file()
            
            counter_key = max(map(int, tweets_fetched_per_day.data.keys()))
            time_since = now_utc - datetime.datetime.fromtimestamp(counter_key, datetime.timezone.utc)
            print(f"Fetched {tweets_fetched_per_day.data[counter_key]} requests since {timeago.format(time_since)}.")

            fetch_timeline_function = lambda: client.get_timeline(count=20)

            while pull_straw(0.3):
                print("Straw pulled true, fetching home timeline...")
                with intercept_twitter_flows():
                    results = await fetch_timeline_function()
                    
                    tweets_fetched_per_day.data[counter_key] += len(results)
                    tweets_fetched_per_day.save_to_file()
                    print(f"Fetched {len(results)} tweets...")
                    
                    fetch_timeline_function = results.next

            all_users_new_tweets = []
            for user_handle in user_handles:
                try:
                    with intercept_twitter_flows():
                        user = await client.get_user_by_screen_name(user_handle)

                    with intercept_twitter_flows():
                        tweets = list(reversed(await user.get_tweets("Tweets", count=40)))

                    tweets_fetched_per_day.data[counter_key] += len(tweets)
                    tweets_fetched_per_day.save_to_file()
                    print("Fetched tweets for user:", user.screen_name, "Total:", len(tweets))

                    new_tweets = [tweet for tweet in tweets if not sent_tweets.exists(tweet) and not sent_tweets.errored.exists(tweet)]

                    print("New tweets to process:", len(new_tweets))
                    all_users_new_tweets.extend(new_tweets)

                    for i, tweet in enumerate(tweets):
                        if sent_tweets.exists(tweet) or sent_tweets.errored.exists(tweet):
                            continue
                        
                        print(f"\n{i+1}. ------ QUEUING NEW TWEET ------")
                        await sent_tweets.add(tweet)

                    sleep_time = round(generate_time_interval(3, 19), 2)
                    print(f"Sleeping for {sleep_time} seconds to avoid rate limiting...")
                    await asyncio.sleep(sleep_time) # Sleep to avoid rate limiting
                except twikit.errors.Unauthorized as e:
                    x_auth_errors._overwrite_and_save({
                        "error": True,
                        "message": str(e),
                        "args": e.args,
                        "X_COOKIES": X_COOKIES,
                        "X_USERNAME": X_USERNAME,
                        "X_EMAIL": X_EMAIL,
                        "X_PASSWORD": X_PASSWORD,
                        "X_FORCE_PUSH_AUTH": X_FORCE_PUSH_AUTH
                    })
                    raise e
                except twikit.errors.TwitterException as e:
                    x_auth_errors._overwrite_and_save({
                        "error": True,
                        "message": str(e),
                        "args": e.args,
                        "X_COOKIES": X_COOKIES,
                        "X_USERNAME": X_USERNAME,
                        "X_EMAIL": X_EMAIL,
                        "X_PASSWORD": X_PASSWORD,
                        "X_FORCE_PUSH_AUTH": X_FORCE_PUSH_AUTH
                    })
                    raise e
                except Exception as e:
                    print(f"Non-twikit error thrown while fetching tweets for user {user_handle}: {e}")
                    traceback.print_exc()
                    continue

            sleep_time = round(generate_time_interval(4 * 60, 40 * 60), 2)
            
            print(f"\n\nSleeping for {round(sleep_time / 60, 2)} minutes before checking for new tweets again...")
            await asyncio.sleep(sleep_time)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received, exiting...")

asyncio.run(main())
