"""语音录制（sounddevice）与 faster-whisper 离线识别。

录音：16kHz 单声道 float32，停止后写成 16bit PCM WAV 临时文件。
识别：faster-whisper 在 CPU 上以 int8 运行，模型懒加载（首次自动下载）。
国内网络默认走 hf-mirror.com 镜像下载模型，可用环境变量 HF_ENDPOINT 覆盖。
"""
import os
import tempfile
import threading
import wave

import numpy as np
from PySide6.QtCore import QObject, Signal

SAMPLE_RATE = 16000

# 国内直连 HuggingFace 经常超时，默认使用镜像站加速模型下载；
# 禁用 hf-xet（xet 后端会绕过镜像直连官方 CAS 服务器导致 401）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


class VoiceRecorder(QObject):
    """按住录音、松开停止。start/stop 均由快捷键信号驱动（GUI 线程）。"""

    started = Signal()
    stopped = Signal(str)   # 录制完成的 wav 文件路径
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stream = None
        self._frames = []
        self._lock = threading.Lock()
        self._wav_path = os.path.join(tempfile.gettempdir(), "automemo_voice.wav")

    @property
    def is_recording(self):
        return self._stream is not None

    def start(self):
        import sounddevice as sd

        with self._lock:
            if self._stream is not None:
                return
            self._frames = []
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    callback=self._on_audio,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                self.error.emit(f"无法打开麦克风：{exc}")
                return
        self.started.emit()

    def _on_audio(self, indata, _frames, _time, _status):
        self._frames.append(indata.copy())

    def stop(self):
        with self._lock:
            if self._stream is None:
                return
            self._stream.stop()
            self._stream.close()
            self._stream = None
            frames, self._frames = self._frames, []
        if frames:
            audio = np.concatenate(frames, axis=0).flatten()
        else:
            audio = np.zeros(0, dtype=np.float32)
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(self._wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        self.stopped.emit(self._wav_path)


class Transcriber(QObject):
    """faster-whisper 离线识别；模型懒加载，识别在后台线程执行。"""

    progress = Signal(str)    # 模型加载/下载进度提示
    finished = Signal(str)    # 识别出的文本
    failed = Signal(str)

    def __init__(self, model_name="base", parent=None):
        super().__init__(parent)
        self.model_name = model_name
        self._model = None
        self._loaded_name = None
        self._model_lock = threading.Lock()

    def set_model(self, model_name):
        """切换模型；下次识别时生效（会重新加载）。"""
        self.model_name = model_name

    def preload(self):
        """后台预加载模型（首次会下载）。"""
        threading.Thread(target=self._get_model, daemon=True).start()

    def transcribe_async(self, wav_path):
        threading.Thread(target=self._run, args=(wav_path,), daemon=True).start()

    def _get_model(self):
        with self._model_lock:
            if self._model is not None and self._loaded_name == self.model_name:
                return self._model
            self.progress.emit(
                f"正在加载语音模型 {self.model_name}（首次需下载约 150MB）…"
            )
            from faster_whisper import WhisperModel

            model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            self._model = model
            self._loaded_name = self.model_name
            self.progress.emit("语音模型就绪")
            return model

    def _run(self, wav_path):
        try:
            model = self._get_model()
            segments, _ = model.transcribe(
                wav_path, language="zh", beam_size=5, vad_filter=True,
                # 引导模型输出简体中文，避免 whisper 中文常见的繁体混杂
                initial_prompt="以下是简体中文普通话的语音转录：",
            )
            text = "".join(seg.text for seg in segments).strip()
            if text:
                self.finished.emit(text)
            else:
                self.failed.emit("没有识别到语音内容，请说话声音大一些或靠近麦克风")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.failed.emit(f"语音识别失败：{exc}")
