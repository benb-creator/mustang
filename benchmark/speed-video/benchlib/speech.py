"""Text-to-speech for the narration: synthesizes exactly the lines `compose` chose (voice-script.json).

Engines (config `speech`):
- `command`: any local engine with a command line, e.g. Piper
  (`[piper, --model, en_US-norman-medium.onnx, --output_file, "{out}"]`, text on stdin) or Coqui TTS. The model file
  is pinned by its SHA-256 (`model`, `model_sha256`), so the voice can't change between videos unnoticed.
- `google`: Google Cloud Text-to-Speech (e.g. `en-US-Chirp3-HD-Orus`), key from the environment variable named in
  `api_key_env` (never logged or written).
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.request
import wave
from pathlib import Path


class SpeechError(Exception):
    pass


class SpeechEngine:
    def __init__(self, spec: dict, language: str):
        self.spec = spec
        self.language = language

    @classmethod
    def create(cls, config, language: str) -> "SpeechEngine":
        spec = dict((config.get("speech") or {}).get(language) or {})
        kind = spec.get("engine")
        if kind == "command":
            return CommandEngine(spec, language, config)
        if kind == "google":
            return GoogleEngine(spec, language)
        raise SpeechError(f"No text-to-speech engine for '{language}': set speech.{language}.engine "
                          f"(command or google) in the config")

    def prepared(self, text: str) -> str:
        for word, spoken in (self.spec.get("lexicon") or {}).items():
            text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
        return text

    def synthesize(self, text: str, out: Path, rate: float = 1.0):
        raise NotImplementedError

    def credit(self) -> dict:
        raise NotImplementedError


class CommandEngine(SpeechEngine):
    def __init__(self, spec: dict, language: str, config):
        super().__init__(spec, language)
        self.command = [str(c) for c in spec["command"]]
        self.model = config.path(spec["model"]) if spec.get("model") else None
        self.model_sha256 = spec.get("model_sha256")
        if self.model is not None:
            digest = hashlib.sha256(self.model.read_bytes()).hexdigest()
            if self.model_sha256 and digest != self.model_sha256:
                raise SpeechError(f"{self.model}: SHA-256 {digest} differs from speech.{language}.model_sha256")
            self.model_sha256 = digest

    def synthesize(self, text: str, out: Path, rate: float = 1.0):
        values = {"out": str(out), "model": str(self.model or ""), "rate": f"{rate:.3f}",
                  "length_scale": f"{float(self.spec.get('length_scale', 1.0)) / rate:.3f}"}
        command = [part.format(**values) for part in self.command]
        result = subprocess.run(command, input=self.prepared(text), capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not out.exists():
            raise SpeechError(f"{command[0]} failed (exit {result.returncode}): {result.stderr[-500:]}")

    def credit(self) -> dict:
        return {"engine": self.spec.get("name") or Path(self.command[0]).name,
                "voice": self.spec.get("voice") or (self.model.name if self.model else None),
                "model_sha256": self.model_sha256, "license": self.spec.get("license")}


class GoogleEngine(SpeechEngine):
    def synthesize(self, text: str, out: Path, rate: float = 1.0):
        key = os.environ.get(self.spec.get("api_key_env", "GOOGLE_TTS_API_KEY"))
        if not key:
            raise SpeechError(f"Environment variable {self.spec.get('api_key_env', 'GOOGLE_TTS_API_KEY')} is not set")
        body = {"input": {"text": self.prepared(text)},
                "voice": {"languageCode": self.spec.get("language_code", "en-US"), "name": self.spec["voice"]},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000,
                                "speakingRate": float(self.spec.get("speaking_rate", 1.0)) * rate}}
        request = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize",
                                         data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "X-Goog-Api-Key": key})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                audio = base64.b64decode(json.loads(response.read())["audioContent"])
        except Exception as ex:
            raise SpeechError(f"Google Text-to-Speech failed: {type(ex).__name__}") from None
        out.write_bytes(audio)

    def credit(self) -> dict:
        return {"engine": "Google Cloud Text-to-Speech", "voice": self.spec["voice"], "license": self.spec.get("license")}


class VoiceSynthesizer:
    """Synthesizes the missing files of a composition's voice-script.json into voice/<lang>/."""

    def __init__(self, engine: SpeechEngine, voice_dir: Path, language: str, progress=print):
        self.engine = engine
        self.target = Path(voice_dir) / language
        self.progress = progress

    @staticmethod
    def chunks(text: str, pauses: list[float]) -> list[tuple[str, float]]:
        """The voice direction's pauses go before the last sentences: one pause → before the last sentence."""
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
        if not pauses or len(sentences) < 2:
            return [(text, 0.0)]
        pauses = pauses[-(len(sentences) - 1):]
        first = len(sentences) - len(pauses)
        out = [(" ".join(sentences[:first]), 0.0)]
        out += [(sentence, pause) for sentence, pause in zip(sentences[first:], pauses)]
        return out

    def synthesize(self, entry: dict, out: Path):
        direction = entry.get("direction") or {}
        rate = float(direction.get("rate", 1.0))
        pieces = self.chunks(entry["text"], [float(p) for p in direction.get("pauses_s") or []])
        if len(pieces) == 1:
            self.engine.synthesize(entry["text"], out, rate)
            return
        parts = []
        for k, (text, pause) in enumerate(pieces):
            part = out.with_suffix(f".part{k}.wav")
            self.engine.synthesize(text, part, rate)
            parts.append((part, pause))
        with wave.open(str(parts[0][0])) as first:
            params = first.getparams()
        with wave.open(str(out), "wb") as target:
            target.setparams(params)
            for part, pause in parts:
                target.writeframes(b"\0" * int(pause * params.framerate) * params.sampwidth * params.nchannels)
                with wave.open(str(part)) as w:
                    target.writeframes(w.readframes(w.getnframes()))
                part.unlink()

    def run(self, script: list[dict], replace: bool = False) -> dict:
        self.target.mkdir(parents=True, exist_ok=True)
        made = []
        for entry in script:
            out = self.target / entry["file"]
            if out.exists() and not replace:
                continue
            self.progress(f"  {entry['file']}: {entry['text']}")
            self.synthesize(entry, out)
            with wave.open(str(out)) as w:
                made.append({"file": entry["file"], "seconds": round(w.getnframes() / w.getframerate(), 2)})
        credit = self.engine.credit()
        (self.target / "credit.json").write_text(json.dumps(credit, indent=2), encoding="utf-8")
        return {"made": made, "credit": credit}
