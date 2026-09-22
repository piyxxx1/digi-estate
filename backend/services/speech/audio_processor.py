import audioop
import base64
import io
import wave


class AudioProcessor:

    @staticmethod
    def pcm_to_wav(
        pcm_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2
    ) -> bytes:
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        return wav_buffer.getvalue()

    @staticmethod
    def wav_to_exotel_pcm(
        wav_b64: str,
        target_sample_rate: int = 16000
    ) -> str:
        """
        Converts WAV from Sarvam to raw 16-bit mono PCM
        for Exotel at 16 kHz.
        """
        try:
            wav_data = base64.b64decode(wav_b64)

            with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
                params = wav_file.getparams()
                frames = wav_file.readframes(params.nframes)

            # Ensure 16-bit PCM
            if params.sampwidth != 2:
                frames = audioop.lin2lin(
                    frames,
                    params.sampwidth,
                    2
                )

            # Convert stereo → mono
            if params.nchannels > 1:
                frames = audioop.tomono(
                    frames,
                    2,
                    1,
                    1
                )

            # Resample only if necessary
            if params.framerate != target_sample_rate:
                frames, _ = audioop.ratecv(
                    frames,
                    2,
                    1,
                    params.framerate,
                    target_sample_rate,
                    None
                )

            return base64.b64encode(frames).decode("utf-8")

        except Exception as e:
            print(f"[AudioProcessor] PCM Conversion Error: {e}")
            return ""

    @staticmethod
    def exotel_pcm_to_sarvam_pcm(
        pcm_payload: str,
        source_sample_rate: int = 16000
    ) -> bytes:
        """
        Converts Exotel incoming PCM to 16 kHz PCM
        for Sarvam STT.
        """
        try:
            audio_bytes = base64.b64decode(pcm_payload)

            if source_sample_rate != 16000:
                resampled_bytes, _ = audioop.ratecv(
                    audio_bytes,
                    2,
                    1,
                    source_sample_rate,
                    16000,
                    None
                )
                return resampled_bytes

            return audio_bytes

        except Exception as e:
            print(f"[AudioProcessor] Resample Error: {e}")
            return b""

    @staticmethod
    def exotel_pcm_to_sarvam_pcm_raw(
        audio_bytes: bytes,
        source_sample_rate: int = 16000
    ) -> bytes:
        """
        Converts raw Exotel PCM to 16 kHz PCM
        for Sarvam STT.
        """
        try:
            if source_sample_rate != 16000:
                resampled_bytes, _ = audioop.ratecv(
                    audio_bytes,
                    2,
                    1,
                    source_sample_rate,
                    16000,
                    None
                )
                return resampled_bytes

            return audio_bytes

        except Exception as e:
            print(f"[AudioProcessor] Raw Resample Error: {e}")
            return audio_bytes