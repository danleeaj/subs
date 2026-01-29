"""
Legacy entry point for the video transcription application.
This module now delegates to the transcribe module.

For CLI usage: python transcribe.py <video_file>
For GUI usage: python gui.py
"""

from transcribe import transcribe_video, main

if __name__ == "__main__":
    main()
