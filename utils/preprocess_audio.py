# This function handles audio preprocessing, depending on length of audio file, to keep it under the size limits of Whisper API.

from pydub import AudioSegment
from pydub.silence import detect_silence
from pathlib import Path

TEMP_DIRECTORY = Path("temp")
TEMP_DIRECTORY.mkdir(exist_ok=True)

def chunk_audio(input_audio_path: Path, target_chunk_duration_ms=1000*60*10, flexibility_ms=None,
                min_silence_len_ms=300, silence_threshold=None) -> None:
    """
    Docstring for chunk_audio
    
    :param input_audio_path: Description
    :type input_audio_path: str
    :param target_chunk_duration_ms: Description
    :param flexibility_ms: Description
    :param min_silence_len_ms: Description
    :param silence_threshold: Description
    """

    audio = AudioSegment.from_file(input_audio_path)

    if silence_threshold is None:
        silence_threshold = audio.dBFS - 16
    
    if flexibility_ms is None:
        flexibility_ms = target_chunk_duration_ms // 5  # If not speciifed, flexibility is 20% of target chunk duration.

    if target_chunk_duration_ms + flexibility_ms > 1000*60*10 and flexibility_ms == None:
        raise ValueError("Target chunk duration plus flexibility cannot exceed 10 minutes. Please manually set flexibility_ms parameter.")

    silences = detect_silence(audio, min_silence_len=min_silence_len_ms, silence_thresh=silence_threshold)
    silence_midpoints = [(start + end) // 2 for start, end in silences]

    chunks = []
    start = 0
    
    while start < len(audio):
        ideal_end = start + target_chunk_duration_ms
        
        if ideal_end >= len(audio):
            chunks.append((start, audio[start:]))
            break
        
        # Look for silence within the flexibility window.
        window_start = ideal_end - flexibility_ms
        window_end = ideal_end + flexibility_ms
        
        candidates = [s for s in silence_midpoints if window_start <= s <= window_end]
        
        if candidates:
            cut_point = min(candidates, key=lambda s: abs(s - ideal_end))
        else:
            cut_point = ideal_end  # If no silence found, then just do x length chunks.
        
        chunks.append((start, audio[start:cut_point]))
        start = cut_point
    
    return chunks

def preprocess_audio(input_audio_path: Path, output_directory: Path) -> None:
    """
    Docstring for preprocess_audio
    
    :param input_audio_path: Description
    :type input_audio_path: str
    :return: Description
    :rtype: str
    """

    audio = AudioSegment.from_file(input_audio_path)
    max_duration_ms = 1000 * 60 * 10

    # start_ms is used downstream when calculating offsets for multiple chunk transcriptions.

    if len(audio) > max_duration_ms:
        chunks = chunk_audio(input_audio_path, target_chunk_duration_ms=max_duration_ms)
        for i, (start_ms, chunk) in enumerate(chunks):
            chunk_file_path = output_directory / f"chunk_{i}_{start_ms}.wav"
            chunk.export(chunk_file_path, format="wav")
    else:
        start_ms = 0
        chunk_file_path = output_directory / f"chunk_1_{start_ms}.wav"
        audio.export(chunk_file_path, format="wav")