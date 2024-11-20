# Home Assistant Add-on: rhasspy-speech

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "rhasspy-speech" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, visit the add-on's Web UI to begin the training process. You must:

1. Download a model by clicking "Download" next to one of the models
2. On the main page, click "Manage" next to a model and then "Edit Sentences"
3. Add your [custom voice command](#custom-voice-commands)
4. Click "Save" and then "Start Training"

Once you have a model trained, it will be automatically discovered by the
Wyoming integration in Home Assistant. To finish the setup, click the following
my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

## Custom voice commands

In the "Edit Sentences" page, add your custom voice commands like this:

```yaml
sentences:
  - turn (on|off) [the] light
```

This will add 4 voice commands:

* turn on light
* turn off light
* turn on the light
* turn off the light

Most of the template syntax from [hassil](https://github.com/home-assistant/hassil) is available. There are many different options available:

```yaml
sentences:
  # Change the output text
  - in: this is what you say
    out: this is what Home Assistant gets
    
  # Use a list (see the 'lists' section below).
  # Excludes the cover entities in {name}.
  - in: turn (on|off) [the] {name}
    excludes_context:
      domain: cover
  
  # Includes just the cover entities in {name}.
  - in: (open|close) [the] {name}
    requires_context:
      domain: cover
      
  - set [a] timer for {minutes} minute[s]
  
lists:
  name:
    values:
      - in: ceiling light
        context:
          domain: light
      - in: garage door
        context:
          domain: cover
  minutes:
    range:
      from: 1
      to: 99
```

### Word Pronunciatons

You can customize the pronunciation of words too:

```yaml
sentences:
  # your sentences
  
words:
  Beyoncé: "bee yawn say"
  HVAC: "h [vac]uum"
```

## Configuration

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
[issue]: https://github.com/home-assistant/addons/issues
[reddit]: https://reddit.com/r/homeassistant
[repository]: https://github.com/rhasspy/hassio-addons
