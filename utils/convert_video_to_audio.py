# This function converts a video file to an audio file using ffmpeg.

import subprocess
from pathlib import Path
from constants import SUPPORTED_INPUT_FORMATS

def convert_video_to_audio(input_video_path: str, output_audio_path: Path) -> None:
    """
    Docstring for convert_video_to_audio
    
    :param input_video_path: Description
    :type input_video_path: str
    :param output_audio_path: Description
    :type output_audio_path: str
    :return: Description
    :rtype: Path
    """

    # We convert input path to Path object for validation.
    input_path = Path(input_video_path)

    if not input_path.exists():
        raise RuntimeError(f"Input video file does not exist: {input_video_path}")
    
    if not input_path.is_file():
        raise RuntimeError(f"Input video path is not a file: {input_video_path}") 
    
    if input_path.suffix.lower().lstrip('.') not in SUPPORTED_INPUT_FORMATS:
        raise RuntimeError(f"Unsupported input video format: {input_path.suffix}. Supported formats are: {SUPPORTED_INPUT_FORMATS}")
    
    if input_path.stat().st_size == 0:
        raise ValueError(f"Input file is empty: {input_path}")

    ffmpeg_cmd_convert_to_audio = [
        'ffmpeg',
        '-i', input_video_path,
        '-vn',
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        '-y',  # Overwrite output file if it exists
        output_audio_path
    ]

    result = subprocess.run(ffmpeg_cmd_convert_to_audio, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error during audio extraction: {result.stderr}")
        raise RuntimeError("ffmpeg audio extraction failed.")
    else:
        print("Audio extraction successful.")