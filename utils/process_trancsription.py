# This function handles transcription of audio files using Whisper API and the merging of multiple subtitle files.

from pathlib import Path

from models import Transcription, FullTranslation, Translation

import re

import json

def create_transcription(input_directory: Path, output_directory: Path, client) -> None:
    """
    Docstring for create_transcription
    
    :param input_directory: Description
    :type input_directory: Path
    :param output_directory: Description
    :type output_directory: Path
    """

    for chunk in input_directory.iterdir():
        audio_file = open(chunk, "rb")

        try:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
            )
        except Exception as e:
            print(f"Error during transcription of {chunk.stem}: {e}")
            raise RuntimeError(f"Transcription failed for chunk: {chunk.stem}")

        with open(output_directory / f"{chunk.stem}.srt", "w") as srt_file:
            srt_file.write(transcription)
            print(f"Transcription saved to: {output_directory}")

def process_transcription(input_directory: Path) -> Transcription:
    """
    Docstring for process_transcription
    
    :param input_directory: Description
    :type input_directory: Path
    :return: Description
    :rtype: Transcription
    """

    srt_files = sorted(input_directory.glob("*.srt"))
    combined_transcription = Transcription(subtitles=[], end_time=0, end_index=0)

    for srt_file in srt_files:
        with open(srt_file, "r", encoding="utf-8") as f:
            srt_content = f.read()
            end_time = int(srt_file.stem.split("_")[-1])
            transcription = Transcription.from_srt(srt_content, end_time=end_time)

            if combined_transcription.subtitles:
                last_index = combined_transcription.end_index
                last_end_time = combined_transcription.end_time

                transcription.offset(offset_ms=last_end_time, offset_index=last_index)

            combined_transcription.subtitles.extend(transcription.subtitles)

            combined_transcription.end_time = transcription.end_time
            combined_transcription.end_index = transcription.end_index

    return combined_transcription