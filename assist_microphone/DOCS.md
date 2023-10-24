# Assist Microphone

Use [Assist](https://www.home-assistant.io/voice_control/) voice assistant with a USB microphone. For example, a USB webcam.

Works with the [openWakeWord add-on](https://my.home-assistant.io/redirect/supervisor_addon/?addon=core_openwakeword).

## Installing the add-on

Select the following my button:

[![Show add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=47701997_assist_microphone&repository_url=https%3A%2F%2Fgithub.com%2Frhasspy%2Fhassio-addons)

or follow these steps to manually install the add-on:

1. Navigate in your Home Assistant frontend to **Settings** > **Add-ons** > **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons.
3. Find the **Assist Microphone** add-on and select it.
4. Select the **Install** button.

## Running the add-on

Before running the add-on, you must configure it with a long-lived access token from Home Assistant.

### To create a token

1. Go to your profile page in Home Assistant.
2. Scroll down to **Long-lived access tokens**.
3. Select **Create token**.
4. Provide a name for the token and select **OK**.
5. Copy the token using the **copy button**.
6. Paste the token into this add-on's configuration page.
7. Select **Save**.

### To run the add on

1. Connect the USB microphone to your Home Assistant server.
2. Restart Home Assistant.
3. Start the **Assist Microphone** add-on.

## Configuration

### Option: `token`

Long-lived access token to communicate with the Home Assistant websocket API.

This is needed because the Supervisor does not currently proxy binary websocket messages. In a future version of Home Assistant OS, this will no longer be necessary.

### Option: `vad`

Voice activity detector to use. webrtcvad is less CPU intensive, but silero is much better.

### Option: `noise_suppression`

Noise suppression level (0 is disabled, 4 is max). A value of 2 is used by default.

### Option: `auto_gain`

Automatic volume boost for microphone (0 is disabled, 31 dbfs is max). A value of 15 is used by default.

### Option: `volume_multiplier`

Multiply microphone volume by fixed value (1.0 = no change, 2.0 = twice as loud). 1.0 is the default.

### Option: `pipeline`

Name of pipeline to run. The preferred pipeline is run by default.

### Option: `wake_buffer_seconds`

Seconds of audio to keep for STT after wake word is detected. If you disable the `awake_sound`, it is recommended to set this value to 0.2. This will let you speak your voice command immediately after saying the wake word. 

### Option: `udp_mic`

True if audio will be sent via UDP on port 5000 (raw 16-bit 16Khz mono PCM).

### Option: `volume`

Playback volume from 0 (mute) to 1 (max).

### Option: `awake_sound`

Path to WAV file to play when wake word is detected (empty to disable).

### Option: `done_sound`

Path to WAV file to play when voice command is finished (empty to disable).

### Option: `host`

Name or IP address of Home Assistant server (default: `homeassistant`)

### Option: `debug_logging`

Enable debug logging.

### Option: `debug_recording_dir`

Directory to save audio for debugging purposes. Should be in /share.

## Support

Got questions?

You have several options to get them answered:

- The [Home Assistant Discord Chat Server][discord].
- The Home Assistant [Community Forum][forum].
- Join the [Reddit subreddit][reddit] in [/r/homeassistant][reddit]

In case you've found an bug, please [open an issue on our GitHub][issue].

[discord]: https://discord.gg/c5DvZ4e
[forum]: https://community.home-assistant.io
[issue]: https://github.com/home-assistant/addons/issues
[reddit]: https://reddit.com/r/homeassistant
[repository]: https://github.com/rhasspy/hassio-addons
