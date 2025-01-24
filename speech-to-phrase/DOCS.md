# Home Assistant Add-on: speech-to-phrase

![logo](logo.png)

[speech-to-phrase](https://github.com/OHF-voice/speech-to-phrase) is a speech-to-text system that recognizes what you say from a set of pre-defined sentences.
It's targeted at lower-end hardware, such as the Raspberry Pi 4.

## Supported languages

* English

See below for a list of supported sentences.

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "rhasspy-speech" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, it should automatically train itself based on your exposed entities, areas, floors, and sentence triggers. Check the logs for the add-on to report "Ready".

Once you have a model trained, it will be automatically discovered by the
Wyoming integration in Home Assistant. To finish the setup, click the following
my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

## English

### Date and Time

- "what time is it?"
- "what's the date?"

### Weather and Temperature

- "what's the weather?"
    - Requires a [weather](https://www.home-assistant.io/integrations/weather/) entity to be configured
- "what's the weather like in New York?"
    - Requires a [weather](https://www.home-assistant.io/integrations/weather/) entity named "New York"
- "what's the temperature?"
    - Requires a [climate](https://www.home-assistant.io/integrations/climate/) entity to be configured
- "what's the temperature of the EcoBee?"
    - Requires a [climate](https://www.home-assistant.io/integrations/climate/) entity named "EcoBee"
    
### Lights

- "turn on/off the lights"
    - Requires voice satellite to be in an [area](https://www.home-assistant.io/docs/organizing/#area)
- "turn on/off standing light"
    - Requires a [light](https://www.home-assistant.io/integrations/light/) entity named "standing light"
- "turn on/off lights in the kitchen"
    - Requires an [area](https://www.home-assistant.io/docs/organizing/#area) named "kitchen"
- "turn on/off lights on the first floor"
    - Requires a [floor](https://www.home-assistant.io/docs/organizing/#floor) named "first floor"
- "set kitchen lights to green"
    - Requires an [area](https://www.home-assistant.io/docs/organizing/#area) named "kitchen" with at least one [light](https://www.home-assistant.io/integrations/light/) entity in it that supports setting color
- "set bed light brightness to 100 percent"
    - Requires a [light](https://www.home-assistant.io/integrations/light/) entity named "bed light" that supports setting brightness
    - Brightness from 10-100 by 10s

### Sensors

- "what is the outdoor humidity?"
    - Requires a [sensor](https://www.home-assistant.io/integrations/sensor/) entity named "outdoor humidity"

### Doors and Windows

- "open/close the garage door"
    - Requires a [cover](https://www.home-assistant.io/integrations/cover/) entity named "garage door"
- "is the garage door open/closed?"
    - Requires a [cover](https://www.home-assistant.io/integrations/cover/) entity named "garage door"
    
### Locks

- "lock/unlock the front door"
    - Requires a [lock](https://www.home-assistant.io/integrations/lock/) entity named "front door"
- "is the front door locked/unlocked?"
    - Requires a [lock](https://www.home-assistant.io/integrations/lock/) entity named "front door"

### Media

- "pause"
    - Requires a [media player](https://www.home-assistant.io/integrations/media_player/) entity that is playing
- "resume"
    - Requires a [media player](https://www.home-assistant.io/integrations/media_player/) entity that is paused
- "next"
    - Requires a [media player](https://www.home-assistant.io/integrations/media_player/) entity to that is playing and supports next track

### Timers

- "set a timer for five minutes"
    - minutes from 1-10, 15, 20, 30, 40, 45, 50-100 by 10s
- "set a timer for thirty seconds"
    - seconds from 10-100 by 10s
- "set a timer for three hours and ten minutes"
    - hours from 1-100
- "pause/resume timer"
- "cancel timer"
- "cancel all timers"
- "timer status"

### Scenes and Scripts

- "run party time"
    - Requires a [script](https://www.home-assistant.io/integrations/script/) named "party time"
- "activate mood lighting"
    - Requires a [scene](https://www.home-assistant.io/integrations/scene/) named "mood lighting"

### Miscellaneous

- "nevermind"


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
