# Home Assistant Add-on: whisper.cpp

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "whisper.cpp" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, it will be automatically discovered
by the Wyoming integration in Home Assistant. To finish the setup,
click the following my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

## Models

Models are automatically downloaded from [HuggingFace](https://huggingface.co/ggerganov/whisper.cpp) and put into `/data`.

Models with `.en` in their name are English-only, while models without will work for any of the [supported languages](https://github.com/rhasspy/wyoming-whisper-cpp/blob/476b0e631392034a94196eb578b3d0a60164af53/whisper.cpp/whisper.cpp#L251).

If the model name contains something like `-q5_1`, then it is a quantized (compressed) version of the original. These are smaller and run faster, though possibly with a loss in quality. Try quantized models first, and only use the non-quantized models if you have transcription errors.


## Configuration

### Option: `model`

Name of the model to use. See the [models](#models) section for more details.

### Option: `language`

Default language to use from the list of [supported languages](https://github.com/rhasspy/wyoming-whisper-cpp/blob/476b0e631392034a94196eb578b3d0a60164af53/whisper.cpp/whisper.cpp#L251).

### Option: `beam_size`

Number of simultaneous candidate sentences to consider. Increasing this number will make the model more accurate, but slower.

### Option: `audio_context_base`

A number from 0-1500 that determines how much audio history to consider when processing. Increasing this number will make the model more accurate, but slower. If the number is too small, you may get repeated text or times when the model takes **much** longer to respond.

### Option: `debug_logging`

Enable debug logging.

## Support

Got questions?

You have several options to get them answered:

- The [Home Assistant Discord Chat Server][discord].
- The Home Assistant [Community Forum][forum].
- Join the [Reddit subreddit][reddit] in [/r/homeassistant][reddit]

In case you've found an bug, please [open an issue on our GitHub][issue].

[discord]: https://discord.gg/c5DvZ4e
[forum]: https://community.home-assistant.io
[issue]: https://github.com/rhasspy/hassio-addons/issues
[reddit]: https://reddit.com/r/homeassistant
[repository]: https://github.com/rhasspy/hassio-addons
