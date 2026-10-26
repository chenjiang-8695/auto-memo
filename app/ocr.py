"""Windows 内置 OCR：QImage -> PNG -> SoftwareBitmap -> OcrEngine。

使用系统自带 Windows.Media.Ocr API（需 Win10/11），无需联网、无需安装额外模型。
识别在后台线程中执行，通过 asyncio 驱动 winsdk 的异步接口。
"""
import asyncio
import ctypes
import re
import threading

from PySide6.QtCore import QBuffer, QIODevice, QObject, Signal

# Windows OCR 会在相邻中文字符之间插入空格，去掉以更贴合原文
_CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\s+"
                        r"(?=[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])")


class OcrEngine(QObject):
    finished = Signal(str)   # 识别出的文本
    failed = Signal(str)

    def recognize_async(self, qimage):
        threading.Thread(target=self._run, args=(qimage,), daemon=True).start()

    def _run(self, qimage):
        try:
            # WinRT 要求线程先初始化 COM（多线程套间），否则底层会直接崩溃
            ctypes.windll.combase.RoInitialize(1)  # RO_INIT_MULTITHREADED
            text = asyncio.run(self._ocr(qimage))
            text = (text or "").strip()
            if text:
                self.finished.emit(text)
            else:
                self.failed.emit("未识别到文字，请框选更清晰的区域")
        except Exception as exc:
            self.failed.emit(f"OCR 识别失败：{exc}")

    async def _ocr(self, qimage):
        # QImage -> PNG 字节（QImage/QBuffer 均为非 GUI 线程安全类型）
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        qimage.save(buffer, "PNG")
        png_bytes = bytes(buffer.data())
        buffer.close()

        from winsdk.windows.graphics.imaging import BitmapDecoder
        from winsdk.windows.globalization import Language
        from winsdk.windows.media.ocr import OcrEngine as WinOcr
        from winsdk.windows.storage.streams import (
            DataWriter,
            InMemoryRandomAccessStream,
        )

        # PNG 字节 -> IRandomAccessStream
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(png_bytes)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        # 优先简体中文语言包，其次用户配置语言
        engine = None
        zh = Language("zh-Hans-CN")
        if WinOcr.is_language_supported(zh):
            engine = WinOcr.try_create_from_language(zh)
        if engine is None:
            engine = WinOcr.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError(
                "系统没有可用的 OCR 语言包，请在 Windows 设置中安装中文语言包"
            )

        result = await engine.recognize_async(bitmap)
        # 逐行清理中文字符间的多余空格
        lines = [_CJK_SPACE.sub("", line) for line in result.text.splitlines()]
        return "\n".join(line for line in lines if line.strip())
