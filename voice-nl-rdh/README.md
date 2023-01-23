# Dutch Text to Speech Voice (rdh)

Voice and vocoder models for [larynx](https://github.com/rhasspy/larynx) based on the free [rdh dataset](https://github.com/r-dh/dutch-vl-tts).

[Samples](https://github.com/rhasspy/nl_larynx-rdh/tree/master/samples)

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
