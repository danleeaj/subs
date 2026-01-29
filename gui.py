"""
GUI module for the video transcription application.
Provides drag and drop functionality for video files and manages the transcription process.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from pathlib import Path
from typing import Callable
import threading
import queue

from constants import SUPPORTED_INPUT_FORMATS


class TranscriptionGUI:
    """Main GUI class for the video transcription application."""

    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Video Transcription")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)

        self.files: list[Path] = []
        self.is_processing = False
        self.message_queue: queue.Queue = queue.Queue()

        self._setup_ui()
        self._setup_drag_drop()
        self._poll_messages()

    def _setup_ui(self):
        """Set up the user interface components."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Drop zone frame
        self.drop_frame = ttk.LabelFrame(main_frame, text="Drop Video Files Here", padding="20")
        self.drop_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Drop zone label
        self.drop_label = ttk.Label(
            self.drop_frame,
            text="Drag and drop video files here\n\nor",
            justify=tk.CENTER,
            font=("TkDefaultFont", 11)
        )
        self.drop_label.pack(pady=(20, 10))

        # Browse button
        self.browse_btn = ttk.Button(
            self.drop_frame,
            text="Browse Files",
            command=self._browse_files
        )
        self.browse_btn.pack(pady=(0, 10))

        # Supported formats label
        formats_text = f"Supported formats: {', '.join(SUPPORTED_INPUT_FORMATS)}"
        self.formats_label = ttk.Label(
            self.drop_frame,
            text=formats_text,
            foreground="gray"
        )
        self.formats_label.pack(pady=(0, 10))

        # File list frame
        list_frame = ttk.LabelFrame(main_frame, text="Selected Files", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # File listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(list_container, height=6, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Remove button
        self.remove_btn = ttk.Button(
            list_frame,
            text="Remove Selected",
            command=self._remove_selected
        )
        self.remove_btn.pack(anchor=tk.E, pady=(5, 0))

        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            progress_frame,
            textvariable=self.status_var,
            foreground="gray"
        )
        self.status_label.pack(anchor=tk.W, pady=(5, 0))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(
            button_frame,
            text="Start Transcription",
            command=self._start_transcription
        )
        self.start_btn.pack(side=tk.RIGHT)

        self.clear_btn = ttk.Button(
            button_frame,
            text="Clear All",
            command=self._clear_all
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def _setup_drag_drop(self):
        """Configure drag and drop functionality."""
        # Register drop target on the drop frame
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_frame.dnd_bind('<<DragEnter>>', self._on_drag_enter)
        self.drop_frame.dnd_bind('<<DragLeave>>', self._on_drag_leave)

        # Also register on the root window for convenience
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._on_drop)

    def _on_drop(self, event):
        """Handle file drop event."""
        # Parse dropped file paths (handles spaces in filenames)
        files_str = event.data

        # tkinterdnd2 returns paths wrapped in {} if they contain spaces
        # and separated by spaces otherwise
        file_paths = []
        if '{' in files_str:
            # Parse paths with braces
            import re
            file_paths = re.findall(r'\{([^}]+)\}|(\S+)', files_str)
            file_paths = [p[0] or p[1] for p in file_paths]
        else:
            file_paths = files_str.split()

        self._add_files(file_paths)
        self._on_drag_leave(event)

    def _on_drag_enter(self, event):
        """Visual feedback when dragging over drop zone."""
        self.drop_label.configure(foreground="blue")

    def _on_drag_leave(self, event):
        """Reset visual feedback when leaving drop zone."""
        self.drop_label.configure(foreground="black")

    def _browse_files(self):
        """Open file browser dialog."""
        filetypes = [
            ("Video files", " ".join(f"*.{fmt}" for fmt in SUPPORTED_INPUT_FORMATS)),
            ("All files", "*.*")
        ]
        files = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=filetypes
        )
        if files:
            self._add_files(files)

    def _add_files(self, file_paths: list[str]):
        """Add valid video files to the list."""
        added_count = 0
        for file_path in file_paths:
            path = Path(file_path)
            # Check if it's a supported format
            if path.suffix.lower().lstrip('.') in SUPPORTED_INPUT_FORMATS:
                if path not in self.files and path.exists():
                    self.files.append(path)
                    self.file_listbox.insert(tk.END, path.name)
                    added_count += 1
            else:
                messagebox.showwarning(
                    "Unsupported Format",
                    f"'{path.name}' is not a supported video format.\n"
                    f"Supported formats: {', '.join(SUPPORTED_INPUT_FORMATS)}"
                )

        if added_count > 0:
            self.status_var.set(f"{len(self.files)} file(s) selected")

    def _remove_selected(self):
        """Remove selected files from the list."""
        selected_indices = list(self.file_listbox.curselection())
        # Remove in reverse order to maintain correct indices
        for index in reversed(selected_indices):
            self.file_listbox.delete(index)
            del self.files[index]

        self.status_var.set(f"{len(self.files)} file(s) selected" if self.files else "Ready")

    def _clear_all(self):
        """Clear all files from the list."""
        self.files.clear()
        self.file_listbox.delete(0, tk.END)
        self.progress_var.set(0)
        self.status_var.set("Ready")

    def _start_transcription(self):
        """Start the transcription process for all files."""
        if not self.files:
            messagebox.showinfo("No Files", "Please add video files first.")
            return

        if self.is_processing:
            messagebox.showinfo("Processing", "Transcription is already in progress.")
            return

        self.is_processing = True
        self._set_ui_state(enabled=False)

        # Start transcription in a separate thread
        thread = threading.Thread(target=self._run_transcription, daemon=True)
        thread.start()

    def _run_transcription(self):
        """Run transcription process in background thread."""
        from transcribe import transcribe_video

        total_files = len(self.files)

        for i, file_path in enumerate(self.files):
            file_num = i + 1
            # Calculate base progress for this file (each file gets an equal portion)
            file_base_progress = (i / total_files) * 100
            file_portion = 100 / total_files

            self._update_status(f"Processing {file_num}/{total_files}: {file_path.name}")
            self._update_progress(file_base_progress)

            def make_progress_callback(base: float, portion: float, num: int, name: str):
                """Create a callback closure with captured values."""
                def callback(msg: str, percent: int):
                    # Calculate overall progress: base + (step_percent * file_portion / 100)
                    overall_progress = base + (percent * portion / 100)
                    self._update_progress(overall_progress)
                    self._update_status(f"[{num}/{total_files}] {name}: {msg}")
                return callback

            try:
                transcribe_video(
                    str(file_path),
                    progress_callback=make_progress_callback(
                        file_base_progress, file_portion, file_num, file_path.name
                    )
                )
                self._update_status(f"Completed {file_num}/{total_files}: {file_path.name}")
            except Exception as e:
                self._update_status(f"Error processing {file_path.name}: {str(e)}")
                self.message_queue.put(("error", f"Error processing {file_path.name}:\n{str(e)}"))

        self._update_progress(100)
        self._update_status(f"Finished processing {total_files} file(s)")
        self.message_queue.put(("done", None))

    def _update_status(self, message: str):
        """Thread-safe status update."""
        self.message_queue.put(("status", message))

    def _update_progress(self, value: float):
        """Thread-safe progress update."""
        self.message_queue.put(("progress", value))

    def _poll_messages(self):
        """Poll message queue for updates from worker thread."""
        try:
            while True:
                msg_type, msg_data = self.message_queue.get_nowait()

                if msg_type == "status":
                    self.status_var.set(msg_data)
                elif msg_type == "progress":
                    self.progress_var.set(msg_data)
                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)
                elif msg_type == "done":
                    self.is_processing = False
                    self._set_ui_state(enabled=True)
                    messagebox.showinfo(
                        "Complete",
                        "Transcription complete!\nSubtitle files have been saved next to the original videos."
                    )
        except queue.Empty:
            pass

        # Schedule next poll
        self.root.after(100, self._poll_messages)

    def _set_ui_state(self, enabled: bool):
        """Enable or disable UI elements during processing."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.browse_btn.configure(state=state)
        self.remove_btn.configure(state=state)
        self.start_btn.configure(state=state)
        self.clear_btn.configure(state=state)

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Entry point for the GUI application."""
    app = TranscriptionGUI()
    app.run()


if __name__ == "__main__":
    main()
