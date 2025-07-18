# Home Assistant Add-on: stt-fallback

Home Assistant add-on that uses [speech-to-text entities](https://www.home-assistant.io/integrations/stt) for fallback.

Runs a [wyoming](https://github.com/OHF-Voice/wyoming/) speech-to-text (STT) server that tries STT entities in order until one succeeds.

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "stt-fallback" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed, enter your speech-to-text entity ids in the configuration (separated by spaces). For example:

```
stt.speech_to_phrase stt.home_assistant_cloud
```

will first try [Speech-to-Phrase](https://github.com/OHF-voice/speech-to-phrase) and fall back to Home Assistant Cloud if it fails.

The fallback STT server will be automatically discovered by the Wyoming integration in Home Assistant. To finish the setup, click the following my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

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
