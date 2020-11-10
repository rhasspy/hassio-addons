# Russian Text to Speech Voice (nikolaev)

Voice and vocoder models for [larynx](https://github.com/rhasspy/larynx) based on the free [M-AI Labs dataset](https://www.caito.de/2019/01/the-m-ailabs-speech-dataset/).

## Usage

Run a web server at http://localhost:5002

```sh
$ docker run -it -p 5002:5002 \
    --device /dev/snd:/dev/snd \
    rhasspy/larynx:ru-nikolaev-1
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
