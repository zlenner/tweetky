# tweeto-whatsapp-channel

Accounts on Twitter often post international news and other updates faster + more accurate versions of them. I wanted to bring that level of reliability and information to WhatsApp because:

a) WhatsApp has lesser amounts of other, distracting brainrot.
b) Many people don't use Twitter, and are instead informed with an abundance of misinformation thanks to "the WhatsApp forwards".

Supports images/videos/gifs... texts are intentionally posted late (but within an hour) to avoid being banned.

## You can use this code to

very easily, set up a simple automated system that uses your Twitter account to fetch tweets from one or more handles + automatically post them to a channel or chat of your choice.

## You must have

Basic coding knowledge and know how to host docker apps on plug-and-play servers like Vercel... but I'll be searching (although passively) for ways I can make this require *zero* coding knowledge.

If you're into that, follow this repo. I might post an update sometime.

## The technical deets.

You need a .env file with the following ENV variables.

### Twitter/X Authentication
ENV variables used to login to your Twitter account.

For the non-technically inclined, these details are stored only wherever you paste them, on your computer or the server you run the app on.

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `X_USERNAME` | ✅ **Yes** | Your Twitter/X username or email | `zlenner_` |
| `X_EMAIL` | ✅ **Yes** | Your Twitter/X email address | `your.email@example.com` |
| `X_PASSWORD` | ✅ **Yes** | Your Twitter/X password | `your_secure_password` |
| `X_COOKIES` | ✅ **Yes** | Base64 encoded Twitter/X session cookies for persistent login | `eyJjb29raWVzIjogWy4uLl19...` |
| `X_HANDLES_TO_WATCH` | ⚠️ **Optional** | Single handle or a comma-separated string of X handles to watch and pull tweets from. | `DropSiteNews,BBCNews` OR just `DropSiteNews` |

Either one of (`X_USERNAME`, `X_EMAIL`, and `X_PASSWORD`) OR `X_COOKIES` is required.

### WhatsApp API Configuration

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `CHANNEL_ID` | ✅ **Yes** | WhatsApp phone number or channel ID to send messages to. | `16754393058@s.whatsapp.net` OR `923000000000@s.whatsapp.net` |

CHANNEL_ID is an internal WhatsApp ID format for chats.

1. For individual chats, it is the full international number + `@s.whatsapp.net`.
2. For channels it is the random ID of the channel + `@newsletter`.
3. For groups it's the random ID of the channel + `@g.us`.

The channel ID can be found from the View Contacts API, also accessable from our WhatsApp UI (will explain later).

### Browser Configuration
| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `X_USER_AGENT` | ⚠️ **Optional** | Custom user agent string for Twitter/X requests. Best to copy-paste your computer's. | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36` |

## HOW TO GET STARTED.

1. Create a .env file and fill out the required ENV variables. At least the ones you can.

2. If you want to run this locally, clone this repo `git clone https://github.com/zlenner/tweeto-whatsapp-channel`, turn on docker, and enter the command `docker-compose up --build` in the same directory as the repo.

3. Should be up and running! First navigate to the local URL provided from the terminal with the message `Login to WhatsApp @ ...`.

4. This app works by reverse-engineering WhatsApp Web's API. Use your phone's "linked devices" feature on WhatsApp to scan the QR code and login.

5. WhatsApp should be working now. If you have a channel whose ID you want to look up, navigate to the same URL minus the path (For example if it's `localhost:3000/path/to/qr_code.png` go to `localhost:3000`), and just scroll down to `List Newsletters`.

6. Now's the time to setup X. Put in the env variables for `X_USERNAME`, `X_PASSWORD` and `X_EMAIL`. If that doesn't work (gives the LoginFlow error below) - see `Troubleshooting` below.

## If run on a server

1. Make sure to attach a persistent volume to the app, because otherwise neither will the X cookies be persisted between starts (this point is moot if you have the `X_COOKIES` variable set)... and neither will the tweets already sent be saved. Which means app will send a stream of duplicate tweets every time it's restarted.

2. If internal networking of the server isn't working properly and you need to tweak the `WHATSAPP_API_URL`... be carefuly not to expose it publicly for too long, and if you do, no HTTP + secure username and password. Be thorough about security like would be in any app!

## Troubleshooting.

If you get the error, `flow name LoginFlow is currently not accessible` - it means Twitter is blocking your requests based on a problematic User Agent or IP.

Use a real user agent like from your own browser + try running the app locally (as it will have a residential IP) and copy-paste the `X_COOKIE` variable generated there into the server's ENV variable.

This is a pretty long-term fix. X doesn't seem to invalidate cookies for the week I've had this app test-running.

## Lastly, an example.

I made a DropSite channel with tweets sourced from their X account... go check it out. They've been pretty on-time and are a reliable source for the Iran-Israel conflict.

[https://whatsapp.com/channel/0029VbAfFCB3WHTaPAAC7n1V](https://whatsapp.com/channel/0029VbAfFCB3WHTaPAAC7n1V)
