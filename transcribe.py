"""
Core transcription module.
Provides the main transcription function that can be called from GUI or CLI.
"""

from dotenv import load_dotenv
import utils.convert_video_to_audio as v2a
from utils.preprocess_audio import preprocess_audio
from utils.process_trancsription import create_transcription, process_transcription

import static_ffmpeg

from openai import OpenAI

from pathlib import Path
from uuid import uuid4, UUID
from typing import Callable, Optional


def transcribe_video(
    input_file_path: str,
    progress_callback: Optional[Callable[[str], None]] = None
) -> tuple[Path, Path, Path]:
    """
    Transcribe a video file and generate subtitle files.

    Args:
        input_file_path: Path to the input video file.
        progress_callback: Optional callback function to receive progress updates.

    Returns:
        Tuple of paths to the generated subtitle files (english, chinese, bilingual).

    Raises:
        RuntimeError: If ffmpeg setup fails.
        Exception: If video to audio conversion fails.
    """
    def update_progress(message: str):
        """Send progress update if callback is provided."""
        if progress_callback:
            progress_callback(message)
        print(message)

    # Define the final output path where subtitles will be saved.
    input_path: Path = Path(input_file_path)

    output_srt_english = input_path.with_stem(f"{input_path.stem}_en").with_suffix(".srt")
    output_srt_chinese = input_path.with_stem(f"{input_path.stem}_zh").with_suffix(".srt")
    output_srt_bilingual = input_path.with_stem(f"{input_path.stem}_en_zh").with_suffix(".srt")

    # Create temp directory with unique identifier for this run.
    id: UUID = uuid4()
    TEMP_DIRECTORY: Path = Path("temp").joinpath(str(id))
    TEMP_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Declare all temp file paths.
    TEMP_DIR_AUDIO_FILE: Path = TEMP_DIRECTORY / "1_audio_file"
    TEMP_FILE_AUDIO_FILE: Path = TEMP_DIR_AUDIO_FILE / "temp_audio.wav"
    TEMP_DIR_AUDIO_CHUNKS: Path = TEMP_DIRECTORY / "2_audio_chunks"
    TEMP_DIR_WHISPER_OUTPUT: Path = TEMP_DIRECTORY / "3_whisper_output"
    TEMP_DIR_SRT_OUTPUT: Path = TEMP_DIRECTORY / "4_srt_output"
    TEMP_FILE_SRT_OUTPUT: Path = TEMP_DIR_SRT_OUTPUT / "temp_srt.srt"
    TEMP_DIR_TRANSLATED_SRT_OUTPUT: Path = TEMP_DIRECTORY / "5_translated_srt_output"
    TEMP_FILE_TRANSLATED_SRT_OUTPUT: Path = TEMP_DIR_TRANSLATED_SRT_OUTPUT / "temp_translated_srt.srt"

    # Load environmental variables (OPENAI_API_KEY).
    load_dotenv()

    # Set up OpenAI client.
    client = OpenAI()

    # Ensure ffmpeg is set up correctly.
    try:
        static_ffmpeg.add_paths()
    except Exception as e:
        update_progress(f"Failed to add ffmpeg paths: {e}")
        raise RuntimeError("ffmpeg setup failed.")

    # Step 1: Convert video to audio.
    update_progress("Converting video to audio...")
    try:
        TEMP_DIR_AUDIO_FILE.mkdir(exist_ok=True)
        v2a.convert_video_to_audio(input_file_path, TEMP_FILE_AUDIO_FILE)
        update_progress("Audio extraction complete")
    except RuntimeError as e:
        update_progress(f"Failed to convert video to audio: {e}")
        _cleanup_temp_directory(TEMP_DIRECTORY)
        raise Exception("Failed to convert video to audio. Please ensure the input file is valid.")

    # Step 2: Chunk audio file, if necessary.
    update_progress("Processing audio...")
    TEMP_DIR_AUDIO_CHUNKS.mkdir(exist_ok=True)
    preprocess_audio(TEMP_FILE_AUDIO_FILE, TEMP_DIR_AUDIO_CHUNKS)
    update_progress("Audio processing complete")

    # Clean up step 1 temp files.
    TEMP_FILE_AUDIO_FILE.unlink()
    TEMP_DIR_AUDIO_FILE.rmdir()

    # Step 3: Transcribe audio chunks using Whisper API.
    update_progress("Transcribing audio with Whisper...")
    TEMP_DIR_WHISPER_OUTPUT.mkdir(exist_ok=True)
    create_transcription(TEMP_DIR_AUDIO_CHUNKS, TEMP_DIR_WHISPER_OUTPUT, client)
    update_progress("Transcription complete")

    # Clean up step 2 temp files.
    for chunk_file in TEMP_DIR_AUDIO_CHUNKS.iterdir():
        chunk_file.unlink()
    TEMP_DIR_AUDIO_CHUNKS.rmdir()

    # Step 4: Process and merge transcriptions.
    update_progress("Merging transcriptions...")
    TEMP_DIR_SRT_OUTPUT.mkdir(exist_ok=True)
    combined_transcription = process_transcription(TEMP_DIR_WHISPER_OUTPUT)
    with open(TEMP_FILE_SRT_OUTPUT, "w", encoding="utf-8") as srt_output_file:
        srt_output_file.write(combined_transcription.to_srt())
    update_progress("Transcription merging complete")

    # Clean up step 3 temp files.
    for srt_file in TEMP_DIR_WHISPER_OUTPUT.iterdir():
        srt_file.unlink()
    TEMP_DIR_WHISPER_OUTPUT.rmdir()

    # Step 5: Translate subtitles to Chinese.
    update_progress("Translating to Chinese...")
    TEMP_DIR_TRANSLATED_SRT_OUTPUT.mkdir(exist_ok=True)
    combined_transcription.translate_subtitles(target_language="Chinese", client=client)
    with open(TEMP_FILE_TRANSLATED_SRT_OUTPUT, "w", encoding="utf-8") as translated_srt_output_file:
        translated_srt_output_file.write(combined_transcription.to_srt())
    update_progress("Translation complete")

    # Step 6: Save final outputs.
    update_progress("Saving subtitle files...")

    # Save English subtitles
    with open(output_srt_english, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt())

    # Save Chinese subtitles
    with open(output_srt_chinese, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt(use_translation=True))

    # Save bilingual subtitles
    with open(output_srt_bilingual, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt(is_bilingual=True))

    # Clean up remaining temp files
    _cleanup_temp_directory(TEMP_DIRECTORY)

    update_progress("Done!")

    return output_srt_english, output_srt_chinese, output_srt_bilingual


def _cleanup_temp_directory(temp_dir: Path):
    """Recursively clean up a temporary directory."""
    if not temp_dir.exists():
        return

    for item in temp_dir.iterdir():
        if item.is_dir():
            _cleanup_temp_directory(item)
        else:
            item.unlink()
    temp_dir.rmdir()


def main():
    """CLI entry point - prompts for file path and runs transcription."""
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("Enter the path to the video file: ").strip()

    if not input_file:
        print("No file path provided.")
        sys.exit(1)

    path = Path(input_file)
    if not path.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)

    try:
        english, chinese, bilingual = transcribe_video(input_file)
        print(f"\nSubtitle files created:")
        print(f"  English: {english}")
        print(f"  Chinese: {chinese}")
        print(f"  Bilingual: {bilingual}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
