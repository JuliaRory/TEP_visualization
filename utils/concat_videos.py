import subprocess
import tempfile
import os

def concat_videos_by_order(video_files, order, output_file):
    """
    Склеивает видео в один файл по заданной последовательности индексов.

    :param video_files: список путей к исходным видео
    :param order: список индексов из video_files, определяющий порядок
    :param output_file: путь к итоговому mp4
    """
    # создаём временный файл с порядком для ffmpeg
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as list_file:
        list_filename = list_file.name
        for idx in order:
            path = os.path.abspath(video_files[idx])
            if not os.path.exists(path):
                raise FileNotFoundError(f"Файл не найден: {path}")
            # ffmpeg требует экранировать слеши в Windows
            path = path.replace('\\', '/')
            list_file.write(f"file '{path}'\n")

    # вызываем ffmpeg для склеивания без перекодирования
    cmd = [
        "ffmpeg",
        "-y",  # перезаписывать выходной файл без вопроса
        "-f", "concat",
        "-safe", "0",
        "-i", list_filename,
        "-c", "copy",
        output_file
    ]

    print("Выполняется ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Ошибка ffmpeg:\n", result.stderr)
        raise RuntimeError("Ошибка при склеивании видео")
    else:
        print(f"Видео успешно склеено в {output_file}")

    # удаляем временный файл
    os.remove(list_filename)