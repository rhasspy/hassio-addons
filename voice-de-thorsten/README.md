# German Text to Speech Voice (thorsten)

Voice and vocoder models for [larynx](https://github.com/rhasspy/larynx) based on the free [thorsten dataset](https://github.com/thorstenMueller/deep-learning-german-tts/).

## Usage

Run a web server at http://localhost:5002

```sh
$ docker run -it -p 5002:5002 \
    --device /dev/snd:/dev/snd \
    rhasspy/larynx:de-thorsten-1
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
