import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import winsound
import os
import struct
import tempfile
import wave
import sys
import threading

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.generate_audio import SONG_LIST
from tools.audio_engine.core import save_wav

class AudioPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Heart of Virtue - Audio Player")
        self.root.geometry("900x600")
        
        self.current_song = None
        self.audio_data = None
        self.temp_file = None
        self.is_playing = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main Layout
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Sidebar (Song List)
        sidebar_frame = ttk.Frame(main_paned, width=200)
        main_paned.add(sidebar_frame, weight=1)
        
        ttk.Label(sidebar_frame, text="Songs").pack(pady=5)
        self.song_listbox = tk.Listbox(sidebar_frame)
        self.song_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.song_listbox.bind('<<ListboxSelect>>', self.on_song_select)
        
        for i, song in enumerate(SONG_LIST):
            self.song_listbox.insert(i, song.title)
            
        # Main Content Area
        content_frame = ttk.Frame(main_paned)
        main_paned.add(content_frame, weight=3)
        
        # Controls Frame
        controls_frame = ttk.LabelFrame(content_frame, text="Controls")
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Modifiers
        mod_frame = ttk.Frame(controls_frame)
        mod_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(mod_frame, text="Tempo:").pack(side=tk.LEFT)
        self.tempo_var = tk.DoubleVar(value=1.0)
        self.tempo_scale = ttk.Scale(mod_frame, from_=0.5, to=2.0, variable=self.tempo_var, orient=tk.HORIZONTAL)
        self.tempo_scale.configure(command=lambda v: self.tempo_label.configure(text=f"{float(v):.2f}x"))
        self.tempo_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.tempo_label = ttk.Label(mod_frame, text="1.0x")
        self.tempo_label.pack(side=tk.LEFT)
        
        # Enable keyboard control for tempo slider
        self.tempo_scale.bind('<Button-1>', lambda e: self.tempo_scale.focus_set())
        self.tempo_scale.bind('<Left>', lambda e: self.adjust_tempo(-0.05))
        self.tempo_scale.bind('<Right>', lambda e: self.adjust_tempo(0.05))
        
        mod_frame2 = ttk.Frame(controls_frame)
        mod_frame2.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(mod_frame2, text="Pitch:").pack(side=tk.LEFT)
        self.pitch_var = tk.IntVar(value=0)
        self.pitch_scale = ttk.Scale(mod_frame2, from_=-12, to=12, variable=self.pitch_var, orient=tk.HORIZONTAL)
        self.pitch_scale.configure(command=lambda v: self.pitch_label.configure(text=f"{int(float(v))} semitones"))
        self.pitch_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.pitch_label = ttk.Label(mod_frame2, text="0 semitones")
        self.pitch_label.pack(side=tk.LEFT)
        
        # Enable keyboard control for pitch slider
        self.pitch_scale.bind('<Button-1>', lambda e: self.pitch_scale.focus_set())
        self.pitch_scale.bind('<Left>', lambda e: self.adjust_pitch(-1))
        self.pitch_scale.bind('<Right>', lambda e: self.adjust_pitch(1))
        
        # Buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.render_btn = ttk.Button(btn_frame, text="Render", command=self.render_song)
        self.render_btn.pack(side=tk.LEFT, padx=5)
        
        self.play_btn = ttk.Button(btn_frame, text="Play", command=self.play_song, state=tk.DISABLED)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_song)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_btn = ttk.Button(btn_frame, text="Reset", command=self.reset_modifiers)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(btn_frame, text="Save to File...", command=self.save_song)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        
        # Waveform Visualization
        viz_frame = ttk.LabelFrame(content_frame, text="Waveform")
        viz_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(viz_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_song_select(self, event):
        selection = self.song_listbox.curselection()
        if selection:
            index = selection[0]
            self.current_song = SONG_LIST[index]
            self.status_var.set(f"Selected: {self.current_song.title}")

    def adjust_tempo(self, delta):
        """Adjust tempo by delta amount (for keyboard control)"""
        current = self.tempo_var.get()
        new_value = max(0.5, min(2.0, current + delta))
        self.tempo_var.set(round(new_value, 2))
        self.tempo_label.configure(text=f"{new_value:.2f}x")

    def adjust_pitch(self, delta):
        """Adjust pitch by delta semitones (for keyboard control)"""
        current = self.pitch_var.get()
        new_value = max(-12, min(12, current + delta))
        self.pitch_var.set(new_value)
        self.pitch_label.configure(text=f"{new_value} semitones")

    def render_song(self):
        if not self.current_song:
            messagebox.showwarning("No Song Selected", "Please select a song from the list.")
            return None
        
        self.status_var.set("Rendering...")
        self.root.update()
        
        try:
            tempo = self.tempo_var.get()
            pitch = int(self.pitch_var.get())
            
            data = self.current_song.render(tempo_scale=tempo, pitch_shift=pitch)
            self.audio_data = data
            self.draw_waveform(data)
            self.status_var.set("Render complete.")
            self.play_btn.config(state=tk.NORMAL)  # Enable Play button
            return data
        except Exception as e:
            messagebox.showerror("Render Error", str(e))
            self.status_var.set("Error rendering song.")
            return None

    def play_song(self):
        if not self.audio_data:
            messagebox.showwarning("No Audio", "Please render the song first.")
            return
        
        # Save to temp file for winsound
        try:
            if self.temp_file:
                try:
                    os.unlink(self.temp_file)
                except:
                    pass
            
            fd, path = tempfile.mkstemp(suffix=".wav")
            self.temp_file = path
            
            with wave.open(path, 'w') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(44100)
                f.writeframes(self.audio_data)
            
            os.close(fd)
            
            self.status_var.set("Playing...")
            winsound.PlaySound(self.temp_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.is_playing = True
            
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))

    def stop_song(self):
        winsound.PlaySound(None, 0)
        self.is_playing = False
        self.status_var.set("Stopped.")

    def reset_modifiers(self):
        """Reset tempo and pitch to defaults and re-render if a song was previously rendered"""
        self.tempo_var.set(1.0)
        self.pitch_var.set(0)
        self.tempo_label.configure(text="1.0x")
        self.pitch_label.configure(text="0 semitones")
        
        # Re-render if we have a current song and audio data exists
        if self.current_song and self.audio_data:
            self.render_song()
            self.status_var.set("Reset to defaults and re-rendered.")
        else:
            self.status_var.set("Reset to defaults.")

    def save_song(self):
        if not self.audio_data:
            # Try to render if not already done
            if not self.render_song():
                return

        filename = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav")],
            initialfile=self.current_song.filename if self.current_song else "output.wav"
        )
        
        if filename:
            try:
                with wave.open(filename, 'w') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(44100)
                    f.writeframes(self.audio_data)
                messagebox.showinfo("Success", f"Saved to {filename}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    def draw_waveform(self, data):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        center_y = height / 2
        
        if not data:
            return
            
        # Unpack samples (assuming 16-bit mono)
        num_samples = len(data) // 2
        step = max(1, num_samples // width)
        
        points = []
        for i in range(0, num_samples, step):
            # Read sample
            sample_bytes = data[i*2 : i*2+2]
            if len(sample_bytes) < 2: break
            sample = struct.unpack('h', sample_bytes)[0]
            
            # Normalize to canvas height
            # 16-bit signed is -32768 to 32767
            y = center_y - (sample / 32768.0) * (height / 2)
            x = (i / num_samples) * width
            points.append(x)
            points.append(y)
            
        if points:
            self.canvas.create_line(points, fill="#00ff00")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioPlayerApp(root)
    root.mainloop()
