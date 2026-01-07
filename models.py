# This module defines data models for handling subtitle trancsriptions in SRT format.

from pydantic import BaseModel, Field
from typing import Optional
import re
import json
    
class Translation(BaseModel):
    """
    Represents a single translation entry with an ID and translated text. Used for JSON structured responses from OpenAI.
    """
    id: int
    text: str

class FullTranslation(BaseModel):
    """
    Represents a full translation containing multiple translation entries. Used for JSON structured responses from OpenAI.
    """
    translations: list[Translation]

class Timestamp:
    """
    Represents a timestamp in the SRT format (HH:MM:SS,mmm). Used for parsing and performing arithmetic operations on timestamps.
    """

    def __init__(self, time: str = None, milliseconds: int = None):
        """
        Initialize a Timestamp object. Either a time string or milliseconds must be provided. Internally converts to milliseconds for easier calculations.
        
        :param self: Description
        :param time: The timestamp string in HH:MM:SS,mmm format.
        :type time: str
        :param milliseconds: The timestamp in milliseconds.
        :type milliseconds: int
        """
        if milliseconds is not None:
            self.milliseconds = milliseconds
        elif time is not None:
            self.milliseconds = self._parse(time)
        else:
            self.milliseconds = 0
    
    def _parse(self, time: str) -> int:
        """
        Parse a timestamp string in HH:MM:SS,mmm format to milliseconds.

        :param time: The timestamp string in HH:MM:SS,mmm format.
        :type time: str
        :return: The timestamp in milliseconds.
        :rtype: int
        """
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        match = re.match(pattern, time)
        if not match:
            raise ValueError(f"Invalid timestamp format: {time}")
        hr, min, s, ms = map(int, match.groups())
        total_ms = (hr * 3600 + min * 60 + s) * 1000 + ms
        return total_ms
    
    def __str__(self) -> str:
        """
        Convert the timestamp back to HH:MM:SS,mmm format.

        :return: The timestamp in HH:MM:SS,mmm format.
        :rtype: str
        """
        ms = self.milliseconds % 1000
        s = (self.milliseconds // 1000) % 60
        min = (self.milliseconds // (1000 * 60)) % 60
        hr = self.milliseconds // (1000 * 3600)
        return f"{hr:02}:{min:02}:{s:02},{ms:03}"
    
    def __add__(self, other: "Timestamp") -> "Timestamp":
        """
        Add two Timestamp objects together.

        :param other: The other timestamp to add.
        :type other: "Timestamp"
        :return: A new Timestamp object representing the sum.
        :rtype: Timestamp
        """
        return Timestamp(milliseconds=self.milliseconds + other.milliseconds)

class SubtitleEntry(BaseModel):
    """
    Represents a single subtitle entry in an SRT file. This model includes the timing and the text content of one line of subtitle, used for the parsing and generating of SRT files.
    """

    index: int = Field(..., description="The index number of the subtitle entry.")
    start_time: str = Field(..., description="The start time of the subtitle in HH:MM:SS,mmm format.")
    end_time: str = Field(..., description="The end time of the subtitle in HH:MM:SS,mmm format.")
    text: str = Field(..., description="The text content of the subtitle entry.")
    translation: Optional[str] = Field(None, description="The translation of the subtitle text.")

    def to_srt_block(self, use_translation: bool = False, is_bilingual: bool = False) -> str:
        """
        Convert subtitle entry to SRT block format. Used in Transcription.to_srt() to generate full SRT.
        
        :return: Formatted SRT block string (index, timecodes, text)
        :rtype: str
        """

        content = self.translation if use_translation and self.translation else self.text
        if is_bilingual and self.translation:
            content = f"{self.text}\n{self.translation}"
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{content}\n"
    
    def offset(self, offset_ms: int) -> None:
        """
        Offset the start and end of the subtitle entry by a given number of milliseconds.
        
        :param offset_ms: Number of milliseconds to offset the subtitle times.
        :type offset_ms: int
        """

        start_ts = Timestamp(self.start_time) + Timestamp(milliseconds=offset_ms)
        end_ts = Timestamp(self.end_time) + Timestamp(milliseconds=offset_ms)
        self.start_time = str(start_ts)
        self.end_time = str(end_ts)
    
class Transcription(BaseModel):
    """
    Represents an entire transcription consisting of multiple subtitle entries. This model is used to manage and manipulate a full set of subtitles, including loading from and saving to SRT format.
    """

    subtitles: list[SubtitleEntry] = Field(..., default_factory=list, description="A list of subtitle entries in the transcription.")
    end_time: int = Field(..., description="The end time of the transcription.")
    end_index: int = Field(0, description="The ending index of the transcription subtitles.")
    language: Optional[str] = Field(None, description="The language of the transcription.")

    @classmethod
    def from_srt(cls, srt_content: str, end_time: int) -> "Transcription":
        """
        Parse SRT content to a Transcription object.

        :param srt_content: The SRT content to parse.
        :type srt_content: str
        :param end_time: The end time of the transcription.
        :type end_time: str
        :param end_index: The ending index of the transcription subtitles.
        :type end_index: int
        :return: A Transcription representation of the SRT object.
        :rtype: Transcription
        """

        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, srt_content.strip() + '\n\n', re.DOTALL)

        subtitles = [
            SubtitleEntry(
                index=int(index),
                start_time=start,
                end_time=end,
                text=text.strip(),
            )
            for index, start, end, text in matches
        ]

        end_index = int(subtitles[-1].index) if subtitles else 0

        return cls(subtitles=subtitles, end_time=end_time, end_index=end_index)
    
    def offset(self, offset_ms: int, offset_index: int) -> None:
        """
        Offset the start and end times of all subtitle entries by a given number of milliseconds and all indices by a given offset.

        :param offset_ms: Number of milliseconds to offset the subtitle times.
        :type offset_ms: int
        :param offset_index: Number to offset the subtitle indices.
        :type offset_index: int
        """
        for subtitle in self.subtitles:
            subtitle.offset(offset_ms)
            subtitle.index += offset_index
    
    def to_srt(self, use_translation: bool = False, is_bilingual: bool = False) -> str:
        """
        Docstring for to_srt
        
        :param use_translation: Whether to use the translation text instead of the original text.
        :param is_bilingual: Whether to include both original and translated text.
        :return: SRT formatted string of the transcription.
        :rtype: str
        """
        return "\n".join(sub.to_srt_block(use_translation=use_translation, is_bilingual=is_bilingual) for sub in self.subtitles)
    
    def save_to_file(self, file_path: str) -> None:
        """
        Docstring for save_to_file
        
        :param self: Description
        :param file_path: Description
        :type file_path: str
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_srt())

    def translate_subtitles(self, target_language: str, client, batch_size: int = 30, overlap: int = 5) -> None:
        """
        Translate all subtitles in batches using OpenAI API with context overlap.
        
        :param target_language: Target language for translation
        :param client: OpenAI client instance
        :param batch_size: Number of subtitles to translate per batch
        :param overlap: Number of previous/next subtitles to include for context (not translated)
        """
        for i in range(0, len(self.subtitles), batch_size):
            batch = self.subtitles[i:i + batch_size]
            
            # Get context subtitles (previous and next)
            start_context_idx = max(0, i - overlap)
            end_context_idx = min(len(self.subtitles), i + batch_size + overlap)
            
            previous_context = self.subtitles[start_context_idx:i] if i > 0 else []
            next_context = self.subtitles[i + batch_size:end_context_idx] if i + batch_size < len(self.subtitles) else []
            
            context_before = [
                {'id': sub.index, 'text': sub.text} 
                for sub in previous_context
            ]
            
            texts_to_translate = [
                {'id': sub.index, 'text': sub.text} 
                for sub in batch
            ]
            
            context_after = [
                {'id': sub.index, 'text': sub.text} 
                for sub in next_context
            ]
            
            translation_prompt = f"""
    Translate subtitle dialogue to {target_language}.

    CONTEXT (PREVIOUS {overlap} SUBTITLES - DO NOT TRANSLATE):
    {json.dumps(context_before, indent=2) if context_before else "None"}

    INPUT TO TRANSLATE:
    {json.dumps(texts_to_translate, indent=2)}

    CONTEXT (NEXT {overlap} SUBTITLES - DO NOT TRANSLATE):
    {json.dumps(context_after, indent=2) if context_after else "None"}

    INSTRUCTIONS:
    - ONLY translate the subtitles in "INPUT TO TRANSLATE" section
    - Use context subtitles to maintain dialogue continuity
    - Translate 'text' field naturally for spoken dialogue
    - Preserve line breaks (\\n) within text
    - Keep translations concise for subtitle timing

    OUTPUT (JSON) - ONLY return translations for INPUT TO TRANSLATE items:
    [
    {{"id": 1, "text": "translated text here"}},
    {{"id": 2, "text": "next translation"}}
    ]
    """
                        
            translation = client.responses.parse(
                model="gpt-4o-mini-2024-07-18", 
                input=translation_prompt,
                text_format=FullTranslation
            )
            
            # Update subtitles with translations
            translation_output = translation.output_parsed
            for subtitle in batch:
                translated = self._get_elem_by_id(translation_output, subtitle.index)
                if translated:
                    subtitle.translation = translated.text
                else:
                    subtitle.translation = ""
                    print(f"Warning: No translation found for ID {subtitle.index}")

    @staticmethod
    def _get_elem_by_id(translation: FullTranslation, id: int) -> Translation | None:
        """
        Get translation element by ID.

        :param translation: The full translation object containing all translations.
        :type translation: FullTranslation
        :param id: The ID of the translation element to retrieve.
        :type id: int
        :return: The translation element if found, otherwise None.
        :rtype: Translation | None
        """
        for trans in translation.translations:
            if trans.id == id:
                return trans
        return None

    def __len__(self) -> int:
        return len(self.subtitles)
    
    def __str__(self) -> str:
        return self.to_srt_string()
