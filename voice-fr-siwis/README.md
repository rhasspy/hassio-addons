# French Text to Speech Voice (siwis)

Voice and vocoder models for [larynx](https://github.com/rhasspy/larynx) based on the [SIWIS corpus](https://datashare.is.ed.ac.uk/handle/10283/2353).

## Usage

Run a web server at http://localhost:5002

```sh
$ docker run -it -p 5002:5002 \
    --device /dev/snd:/dev/snd \
    rhasspy/larynx:nl-rdh-1
```

Endpoints:

* `/api/tts` - returns WAV audio for text
    * `GET` with `?text=...`
    * `POST` with text body
* `/api/phonemize` - returns phonemes for text
    * `GET` with `?text=...`
    * `POST` with text body
* `/process` - compatibility endpoint to emulate [MaryTTS](http://mary.dfki.de/)
    * `GET` with `?INPUT_TEXT=...`
