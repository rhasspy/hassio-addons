# Home Assistant Add-on: rhasspy-speech

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "rhasspy-speech" add-on and click it.
3. Click on the "INSTALL" button.

## How to use

After this add-on is installed and running, it should automatically train itself based on the configured language (default is English). Check the logs for the add-on to report "Ready".

You can visit the add-on's Web UI at any time to re-train it or add new voice commands.

Once you have a model trained, it will be automatically discovered by the
Wyoming integration in Home Assistant. To finish the setup, click the following
my button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wyoming)

Alternatively, you can install the Wyoming integration manually, see the
[Wyoming integration documentation](https://www.home-assistant.io/integrations/wyoming/)
for more information.

## Builtin voice commands

By default, the add-on is trained with a limited set of voice commands for Home Assistant ("Include builtin intents" setting). Your exposed entities, areas, and floors are included in these commands ("Download Home Assistant entities" setting).

In the add-on's Web UI, visit the "Intents" page to browse the available voice commands. Use the "Edit Sentences" button on the main page to add custom voice commands.

## Custom voice commands

In the "Edit Sentences" page, add your custom voice commands like this:

```yaml
sentences:
  - "turn (on|off) [the] light"
```

**Tip:** Always use quotes around voice commands to avoid YAML oddities.

This will add 4 possible voice commands:

* turn on light
* turn off light
* turn on the light
* turn off the light

Most of the template syntax from [hassil](https://github.com/home-assistant/hassil) is available. There are many different options available:

```yaml
sentences:
  - a basic voice command

  # Change the output text
  - in: "this is what you say"
    out: "this is what Home Assistant sees"
    
  # Use a list (see the 'lists' section below).
  # Excludes the cover entities in {name}.
  - in: "turn (on|off) [the] {name}"
    excludes_context:
      domain: cover
  
  # Includes just the cover entities in {name}.
  - in: "(open|close) [the] {name}"
    requires_context:
      domain: cover
      
  - "set [a] timer for {minutes} minute[s]"
  
lists:
  name:
    values:
      - in: "ceiling light"
        context:
          domain: light
      - in: "garage door"
        context:
          domain: cover
  minutes:
    range:
      from: 1
      to: 100
      step: 5
```

The `{name}`, `{area}`, and `{floor}` lists are automatically populated with your exposed entities, areas, and floors. If you don't want this, turn off the "Download Home Assistant entities" configuration option.

If you want to use todo lists, you can specify the possible items:

```yaml
lists:
  todo_item:
    values:
      - apples
      - bananas
      - oranges
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

Using square brackets means you only want part of a word's pronunciation. For example, `[vac]uum` is just the "vac" part.

It's also possible to use [phonemes](https://www.ipachart.com/) directly (different for each language):

```yaml
words:
  raxacoricofallipatorius: "/ɹ ˈæ k s ə k ˌɔ ɹ ɪ k ˌɔ f ˈæ l ə p ə t ˈɔ ɹ i ə s/"
```

Note the use of `/` to surround phonemes.

Use the "Lookup words" button in the Web UI to check/guess pronunciations.

## Data

Models and training data are stored in `/share/rhasspy-speech`. If you want to back up your sentences, they are stored in `/share/rhasspy-speech/train/<model>/sentences.yaml`.

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
