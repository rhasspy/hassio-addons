# Spanish Text to Speech Voice (css10)

Voice and vocoder models for [larynx](https://github.com/rhasspy/larynx) based on [CSS10](https://www.kaggle.com/bryanpark/spanish-single-speaker-speech-dataset).

## Usage

Run a web server at http://localhost:5002

```sh
$ docker run -it -p 5002:5002 \
    --device /dev/snd:/dev/snd \
    rhasspy/larynx:es-css10-1
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
