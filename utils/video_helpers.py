import subprocess
import json

def add_silent_audio(input_video, output_video):
        """
        Добавляет к видеофайлу пустую (тихую) аудиодорожку.
        Требует установленного ffmpeg в PATH.
        """

        # Генерируем тихую аудиодорожку нужной длины прямо из ffmpeg
        # -f lavfi -i anullsrc = источник пустого звука
        # -c:v copy = не перекодировать видео
        # -shortest = обрезать аудио по длине видео
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_video,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_video
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except FileNotFoundError:
            raise FileNotFoundError("ffmpeg не найден. Добавь ffmpeg в PATH или укажи полный путь.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Ошибка FFmpeg: {e.stderr.decode() if e.stderr else e}")

        return output_video

def has_audio(path):
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    info = json.loads(result.stdout)

    for stream in info.get("streams", []):
        if stream.get("codec_type") == "audio":
            return True
    
    return False