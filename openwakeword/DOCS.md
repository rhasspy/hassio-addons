# Home Assistant Add-on: openWakeWord

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Find the "openWakeWord" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, it will be automatically discovered
by the Wyoming integration in Home Assistant. To finish the setup,
click the following my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

## Configuration

### Option: `model`

Name of wake word model to use. Available models are:

* `ok_nabu` (default)
* `hey_jarvis`
* `alexa`
* `hey_mycroft`
* `hey_rhasspy`

### Option: `threshold`

Activation threshold (0-1), where higher means fewer activations.  See trigger
level for the relationship between activations and wake word detections.

### Option: `trigger_level`

Number of activations before a detection is registered. A higher trigger level
means fewer detections.

### Option: `noise_suppression`

Noise suppression level with
[webrtc](https://github.com/rhasspy/webrtc-noise-gain), where 0 is disabled
(default) and 4 is the max. Suppresses common sources of noise, such as fans,
but may distort audio. This should be used for low quality microphones, or in
noisy environments where noise suppression is not available on the voice
satellite.

### Option: `auto_gain`

Automatic gain control target dBFS with
[webrtc](https://github.com/rhasspy/webrtc-noise-gain), where 0 is disabled
(default) and 31 is the max. Raises the volume when someone is speaking too
quietly, but may distort audio. This should be used for low quality microphones,
or if the voice satellite is far away and does not have auto-gain functionality.

### Option: `save_audio`

Enable recording of audio to `/share/openwakeword` as WAV files.
**WARNING**: All audio is saved, including before the wake word is spoken, so this option should be disabled to preserve disk space.

### Option: `debug_logging`

Enable debug logging. Useful for seeing satellite connections and each wake word detection in the logs.

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
[repository]: https://github.com/hassio-addons/repository
