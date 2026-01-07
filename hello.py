from dotenv import load_dotenv
import utils.convert_video_to_audio as v2a
from utils.preprocess_audio import preprocess_audio
from utils.process_trancsription import create_transcription, process_transcription

import static_ffmpeg

from openai import OpenAI

from pathlib import Path
from uuid import uuid4, UUID

def main() -> None:

    # We first define the input file path.

    input_file_path: str = "/Users/anjie.wav/Downloads/jeff-谈抑郁&心理治疗.mov"

    # We also define the final output path where subtitles will be saved.
    # This is determined by creating a new file path in the same directory as the input file, with the same name but with a .srt extension.

    input_path: Path = Path(input_file_path)

    output_srt_english = input_path.with_stem(f"{input_path.stem}_en").with_suffix(".srt")
    output_srt_chinese = input_path.with_stem(f"{input_path.stem}_zh").with_suffix(".srt")
    output_srt_bilingual = input_path.with_stem(f"{input_path.stem}_en_zh").with_suffix(".srt")

    # We will also use temp files to store intermediate result, temp files from the previous step will be cleared after the next step succeeds.
    # To account for when, in the future, we might want to run multiple instances in parallel, we'll create a temp directory specific to each run using a unique identifier (UUID).

    id: UUID = uuid4()
    TEMP_DIRECTORY: Path = Path("temp").joinpath(str(id))
    TEMP_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Declare all temp file paths.

    TEMP_DIR_AUDIO_FILE: Path = TEMP_DIRECTORY / "1_audio_file"
    TEMP_FILE_AUDIO_FILE: Path = TEMP_DIR_AUDIO_FILE / "temp_audio.wav"
    TEMP_DIR_AUDIO_CHUNKS: Path = TEMP_DIRECTORY / "2_audio_chunks" # Since there can be multiple audio chunks, this is a directory.
    TEMP_DIR_WHISPER_OUTPUT: Path = TEMP_DIRECTORY / "3_whisper_output" # Since there can be multiple Whisper outputs, this is a directory.
    TEMP_DIR_SRT_OUTPUT: Path = TEMP_DIRECTORY / "4_srt_output"
    TEMP_FILE_SRT_OUTPUT: Path = TEMP_DIR_SRT_OUTPUT / "temp_srt.srt"
    TEMP_DIR_TRANSLATED_SRT_OUTPUT: Path = TEMP_DIRECTORY / "5_translated_srt_output"
    TEMP_FILE_TRANSLATED_SRT_OUTPUT: Path = TEMP_DIR_TRANSLATED_SRT_OUTPUT / "temp_translated_srt.srt"

    # Load environmental variables (should only be OPENAI_API_KEY for now).

    load_dotenv()

    # Set up OpenAI client.

    client = OpenAI()

    # Ensure ffmpeg is set up correctly.
    
    try:
        static_ffmpeg.add_paths()
    except Exception as e:
        print(f"Failed to add ffmpeg paths: {e}")
        raise RuntimeError("ffmpeg setup failed.")

    # Step 1: Convert video to audio.

    try:
        TEMP_DIR_AUDIO_FILE.mkdir(exist_ok=True)
        v2a.convert_video_to_audio(input_file_path, TEMP_FILE_AUDIO_FILE)
        print(f"Audio file created at: {TEMP_FILE_AUDIO_FILE}")
    except RuntimeError as e:
        print(f"Failed to convert video to audio: {e}")
        raise Exception("Failed to convert video to audio. Please ensure the input file is valid.")
    
    # Step 2: Chunk audio file, if necessary.
    # If chunking is not necessary, we will just have one chunk that is the entire audio file.

    TEMP_DIR_AUDIO_CHUNKS.mkdir(exist_ok=True)
    preprocess_audio(TEMP_FILE_AUDIO_FILE, TEMP_DIR_AUDIO_CHUNKS)
    print(f"Audio chunks created at: {TEMP_DIR_AUDIO_CHUNKS}")

    # Clean up step 1 temp files.

    TEMP_FILE_AUDIO_FILE.unlink()
    TEMP_DIR_AUDIO_FILE.rmdir()

    # Step 3: Transcribe audio chunks using Whisper API.

    TEMP_DIR_WHISPER_OUTPUT.mkdir(exist_ok=True)
    create_transcription(TEMP_DIR_AUDIO_CHUNKS, TEMP_DIR_WHISPER_OUTPUT, client)
    print(f"Whisper transcriptions created at: {TEMP_DIR_WHISPER_OUTPUT}")

    # Clean up step 2 temp files.

    for chunk_file in TEMP_DIR_AUDIO_CHUNKS.iterdir():
        chunk_file.unlink()
    TEMP_DIR_AUDIO_CHUNKS.rmdir()

    # Step 4: Process and merge transcriptions. This step will occur regardless of how many chunks there are. This is probably slightly inefficient if there's only one chunk.

    TEMP_DIR_SRT_OUTPUT.mkdir(exist_ok=True)
    combined_transcription = process_transcription(TEMP_DIR_WHISPER_OUTPUT)
    with open(TEMP_FILE_SRT_OUTPUT, "w", encoding="utf-8") as srt_output_file:
        srt_output_file.write(combined_transcription.to_srt())
    print(f"Merged SRT file created at: {TEMP_FILE_SRT_OUTPUT}")

    # Clean up step 3 temp files.

    for srt_file in TEMP_DIR_WHISPER_OUTPUT.iterdir():
        srt_file.unlink()
    TEMP_DIR_WHISPER_OUTPUT.rmdir()

    # Step 5: Translate subtitles to Chinese.

    TEMP_DIR_TRANSLATED_SRT_OUTPUT.mkdir(exist_ok=True)
    combined_transcription.translate_subtitles(target_language="Chinese", client=client)
    with open(TEMP_FILE_TRANSLATED_SRT_OUTPUT, "w", encoding="utf-8") as translated_srt_output_file:
        translated_srt_output_file.write(combined_transcription.to_srt())
    print(f"Translated SRT file created at: {TEMP_FILE_TRANSLATED_SRT_OUTPUT}")

    # Step 6: Save final outputs.

    # Save English subtitles
    with open(output_srt_english, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt())

    # Save Chinese subtitles (already translated)
    with open(output_srt_chinese, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt(use_translation=True))

    # Save bilingual subtitles
    with open(output_srt_bilingual, "w", encoding="utf-8") as f:
        f.write(combined_transcription.to_srt(is_bilingual=True))

if __name__ == "__main__":
    main()