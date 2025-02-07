# Home Assistant Add-on: speech-to-phrase

**NOTE:** This add-on is in beta! Expect things to change and break.

A fast, local speech-to-text system that is personalized with your [Home Assistant](https://www.home-assistant.io/) device names.
It's targeted at lower-end hardware, such as the Raspberry Pi 4 and Home Assistant Green.

Speech-to-phrase is not a general purpose speech recognition system. Instead of answering the question "what did the user say?", it answers "which of the phrases I know did the user say?".
This is accomplished by combining [pre-defined sentence templates](https://github.com/OHF-Voice/speech-to-phrase/tree/main/speech_to_phrase/sentences) with the names of your Home Assistant entities, areas, and floors that have been [exposed to Assist](https://www.home-assistant.io/voice_control/voice_remote_expose_devices/). [Sentence triggers][sentence trigger] are also included automatically.


## Supported languages

Available voice commands:

- [English](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/english.md)
- [Français (French)](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/french.md)
- [Deutsch (German)](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/german.md)
- [Nederlands (Dutch)](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/dutch.md)
- [Spanish (Español)](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/spanish.md)
- [Italian (Italiano)](https://github.com/OHF-Voice/speech-to-phrase/blob/main/docs/italian.md)

## Installation

[![Show add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=47701997_speech-to-phrase&repository_url=https%3A%2F%2Fgithub.com%2Frhasspy%2Fhassio-addons)

Use the "my link" above or manually follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "rhasspy-speech" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, it should automatically train itself based on your exposed entities, areas, floors, and [sentence triggers][sentence trigger].
The add-on will automatically re-train if necessary.


The add-on will be automatically discovered by the Wyoming integration in Home Assistant. To finish the setup, click the following my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

See [the documentation](https://github.com/OHF-voice/speech-to-phrase) for available voice commands.

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
[sentence trigger]: https://www.home-assistant.io/docs/automation/trigger/#sentence-trigger
