# Home Assistant Add-on: snowboy

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on store**.
2. Add the store https://github.com/rhasspy/hassio-addons
2. Find the "snowboy" add-on and click it.
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

### Option: `sensitivity`

Activation threshold (0-1), where higher means fewer activations.

### Option: `debug_logging`

Enable debug logging. Useful for seeing satellite connections and each wake word detection in the logs.

## Custom Wake Words

This add-on will train custom wake words on start-up from WAV audio samples placed in `/share/snowboy/train/<language>/<wake_word>`

To get started, first record 3 samples of your wake word:

```sh
arecord -r 16000 -c 1 -f S16_LE -t wav -d 3 sample1.wav
arecord -r 16000 -c 1 -f S16_LE -t wav -d 3 sample2.wav
arecord -r 16000 -c 1 -f S16_LE -t wav -d 3 sample3.wav
```

Ideally, this should be recorded on the same device you plan to use for wake word recognition (same microphone, etc).

After your 3 samples are recorded, you will need to copy them to your Home Assistant server. You can use the [Samba add-on](https://www.home-assistant.io/common-tasks/supervised/#installing-and-using-the-samba-add-on) to do this.

Copy the WAV files to `/share/snowboy/train/<language>/<wake_word>` where `<language>` is either `en` for English or `zh` for Chinese (other languages are not supported). `<wake_word>` should be the name of your wake word, such as `hey_computer` (spaces in the same are not recommended).

Your directory structure should look like this after copying the samples:

- `/share/snowboy/train/`
    - `en/`
        - `hey_computer/`
            - `sample1.wav`
            - `sample2.wav`
            - `sample3.wav`

Restart the add-on and check the log for a message that your wake word was trained. Enable debug logging in the add-on configuration for more information.

After training, your wake word model (`.pmdl`) will be next to your samples:

- `/share/snowboy/train/`
    - `en/`
        - `hey_computer/`
            - `hey_computer.pmdl`
            - `sample1.wav`
            - `sample2.wav`
            - `sample3.wav`
            
Copy your wake word model (e.g., `hey_computer.pmdl`) to `/share/snowboy` to start using it immediately.

If you'd like to retrain, delete the `.pmdl` file next to your samples and restart the add-on. You will need to copy the new model to `/share/snowboy` again after training.

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
