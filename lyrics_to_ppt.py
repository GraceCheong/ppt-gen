import re
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pptx import Presentation

# ==========================================
# 1. Parsing & Logic Helper Functions 
# ==========================================

def parse_lyrics_text(raw_text):
    lyrics_dict = {}
    blocks = re.split(r'\n\s*\n', raw_text.strip())
    
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue
            
        part_key = lines[0].strip()
        lyrics_content = '\n'.join([line.strip() for line in lines[1:]])
        lyrics_dict[part_key] = lyrics_content
        
    return lyrics_dict

def get_base_key(part_key):
    return re.sub(r"'+$", "", part_key)

def chunk_text(text, max_lines=2):
    if not text:
        return []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    MIN_LINE_THRESHOLD = 6
    
    chunks = []
    i = 0
    while i < len(lines):
        take_lines = max_lines
        if max_lines == 1 and len(lines[i]) <= MIN_LINE_THRESHOLD and i + 1 < len(lines):
            take_lines = 2
            
        chunk_lines = lines[i:i+take_lines]
        chunks.append('\n'.join(chunk_lines))
        i += len(chunk_lines)
                
    return chunks

def set_editable_text(shape, text):
    text_frame = shape.text_frame
    text_frame.clear()

    lines = text.split('\n') if text else [""]
    for idx, line in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if idx == 0 else text_frame.add_paragraph()
        run = paragraph.add_run()
        run.text = line

# ==========================================
# 2. Core PPT Generator Function
# ==========================================

def append_lyrics_to_ppt(prs, song_title, lyrics_text, sequence_str, max_lines_per_slide=2, long_line_threshold=18):
    lyrics_dict = parse_lyrics_text(lyrics_text)
    sequence_list = [part.strip() for part in sequence_str.split('-') if part.strip()]
    
    min_lines = max(1, max_lines_per_slide - 1)
    
    is_long = False
    
    for part in sequence_list:
        base_part = get_base_key(part)
        
        test_text = ""
        if part in lyrics_dict:
            test_text = lyrics_dict[part]
        elif base_part in lyrics_dict:
            test_text = lyrics_dict[base_part]
        else:
            if part.startswith('(') and part.endswith(')'):
                test_text = part[1:-1].strip()
                
        if test_text:
            lines = [L.strip() for L in test_text.split('\n') if L.strip()]
            for L in lines:
                if len(L) >= long_line_threshold:
                    is_long = True
                    break
        if is_long:
            break
            
    if is_long:
        max_lines_per_slide = min_lines
            
    title_layout = None
    lyrics_layout = None
    
    for layout in prs.slide_layouts:
        if "제목" in layout.name:
            title_layout = layout
        if "가사" in layout.name:
            lyrics_layout = layout
            
    if title_layout is None:
        title_layout = prs.slide_layouts[2] if len(prs.slide_layouts) > 2 else prs.slide_layouts[0]
    if lyrics_layout is None:
        lyrics_layout = prs.slide_layouts[3] if len(prs.slide_layouts) > 3 else prs.slide_layouts[0]

    title_slide = prs.slides.add_slide(title_layout)
    for shape in title_slide.placeholders:
        if shape.has_text_frame:
            set_editable_text(shape, song_title)
            break

    for idx, part in enumerate(sequence_list):
        base_part = get_base_key(part)
        
        if part in lyrics_dict:
            display_text = lyrics_dict[part]
        elif base_part in lyrics_dict:
            display_text = lyrics_dict[base_part]
        else:
            if part.startswith('(') and part.endswith(')'):
                display_text = part[1:-1].strip()
            else:
                if idx == 0 and base_part.upper() in ["I", "INTRO"]:
                    continue
                display_text = "-"
            
        chunks = chunk_text(display_text, max_lines_per_slide)
        if not chunks:
            chunks = [""]
            
        for chunk in chunks:
            slide = prs.slides.add_slide(lyrics_layout)
            
            placeholders = [shape for shape in slide.placeholders if shape.has_text_frame]
            placeholders.sort(key=lambda s: getattr(s, 'width', 0) * getattr(s, 'height', 0), reverse=True)
            
            lyrics_placeholder = placeholders[0] if len(placeholders) > 0 else None
            song_title_placeholder = placeholders[1] if len(placeholders) > 1 else None
                            
            if lyrics_placeholder is not None:
                set_editable_text(lyrics_placeholder, chunk)
                
            if song_title_placeholder is not None:
                set_editable_text(song_title_placeholder, song_title)

# ==========================================
# 3. GUI Implementation
# ==========================================

class MultilineDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x350")
        self.transient(parent)
        self.result = None
        
        ttk.Label(self, text=prompt).pack(pady=10)
        self.text_area = scrolledtext.ScrolledText(self, width=45, height=12)
        self.text_area.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Enable closing via X button
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        # Wait for the dialog to be closed
        self.grab_set()
        self.wait_window(self)

    def on_ok(self):
        self.result = self.text_area.get("1.0", tk.END).strip()
        self.destroy()

    def on_cancel(self):
        self.destroy()

class LyricsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lyrics PowerPoint Generator")
        self.geometry("600x450")
        
        self.create_widgets()
        
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def create_widgets(self):
        # Settings Frame
        settings_frame = ttk.LabelFrame(self, text="Settings", padding=(10, 10))
        settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Max Lines Settings
        ttk.Label(settings_frame, text="슬라이드당 최대 줄 수\n(Max lines per slide):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.max_lines_var = tk.IntVar(value=2)
        ttk.Spinbox(settings_frame, from_=1, to=10, textvariable=self.max_lines_var, width=5).grid(row=0, column=1, sticky=tk.W)
        
        # Threshold Settings
        ttk.Label(settings_frame, text="긴 줄 기준 글자 수\n(Long Line Threshold):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.threshold_var = tk.IntVar(value=18)
        ttk.Spinbox(settings_frame, from_=5, to=100, textvariable=self.threshold_var, width=5).grid(row=1, column=1, sticky=tk.W)
        
        # Generate Button
        self.generate_btn = ttk.Button(self, text="Generate PPT", command=self.generate_ppt)
        self.generate_btn.pack(pady=10)
        
        # Log Area
        self.log_area = scrolledtext.ScrolledText(self, width=70, height=12, state=tk.DISABLED)
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
    def log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.update_idletasks()

    def get_manual_lyrics(self, song_title):
        dialog = MultilineDialog(self, "Input Lyrics", f"Please paste the lyrics for '{song_title}' below:")
        return dialog.result or ""

    def get_output_dir(self):
        output_dir = os.path.join(self.base_dir, "out")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def generate_ppt(self):
        self.log("====================================")
        self.log("Starting PPT Generation...")
        
        max_lines_per_slide = self.max_lines_var.get()
        long_line_threshold = self.threshold_var.get()
        
        template_file = os.path.join(self.base_dir, "template.pptx")
        sequence_file = os.path.join(self.base_dir, "sequences.txt")
        
        if not os.path.exists(template_file):
            self.log(f"[Error] Cannot find template PPTX file: '{template_file}'")
            messagebox.showerror("Error", f"Template file missing:\n{template_file}")
            return
            
        try:
            prs = Presentation(template_file)
        except Exception as e:
            self.log(f"[Error] Failed to load template: {e}")
            return

        if os.path.exists(sequence_file):
            self.log(f"[Info] Found 'sequences.txt'. Integrating all songs...\n")
            
            with open(sequence_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                
            for i in range(0, len(lines), 2):
                song_title = lines[i]
                
                if i + 1 < len(lines):
                    sequence_str = lines[i+1]
                else:
                    self.log(f"[Warning] Missing sequence string for '{song_title}'. Skipping...")
                    continue
                    
                lyrics_file = os.path.join(self.base_dir, f"{song_title}.txt")
                
                raw_lyrics = ""
                if os.path.exists(lyrics_file):
                    self.log(f"-> Processing '{song_title}'")
                    with open(lyrics_file, 'r', encoding='utf-8') as f:
                        raw_lyrics = f.read()
                else:
                    self.log(f"[Warning] '{lyrics_file}' Not Found! Prompting manual input...")
                    raw_lyrics = self.get_manual_lyrics(song_title)
                    
                if raw_lyrics:
                    append_lyrics_to_ppt(prs, song_title, raw_lyrics, sequence_str, max_lines_per_slide, long_line_threshold)
                else:
                    self.log(f"   Skipped '{song_title}' (No lyrics provided)")
                
            output_file = os.path.join(self.get_output_dir(), "integrated_lyrics.pptx")
            try:
                prs.save(output_file)
                self.log(f"\n[Success] Created '{output_file}'.\n")
                messagebox.showinfo("Success", f"PPT successfully generated!\nSaved as: out/integrated_lyrics.pptx")
            except Exception as e:
                self.log(f"[Error] Failed to save PPT: {e}")
                
        else:
            self.log(f"[Warning] 'sequences.txt' not found. Falling back to single-song manual mode...\n")
            
            from tkinter import simpledialog
            song_title = simpledialog.askstring("Input", "Enter the Song Title:", parent=self)
            if not song_title:
                self.log("Cancelled single-song mode.")
                return
                
            sequence_str = simpledialog.askstring("Input", "Enter the Sequence (e.g., I-V1-C-Out):", parent=self)
            if not sequence_str:
                self.log("Cancelled single-song mode.")
                return
                
            lyrics_file = os.path.join(self.base_dir, f"{song_title}.txt")
            raw_lyrics = ""
            
            if os.path.exists(lyrics_file):
                self.log(f"[Success] Found '{lyrics_file}' automatically!")
                with open(lyrics_file, 'r', encoding='utf-8') as f:
                    raw_lyrics = f.read()
            else:
                self.log(f"Prompting explicit manual lyrics input for: {song_title}")
                raw_lyrics = self.get_manual_lyrics(song_title)
                
            if raw_lyrics and sequence_str:
                append_lyrics_to_ppt(prs, song_title, raw_lyrics, sequence_str, max_lines_per_slide, long_line_threshold)
                output_file = os.path.join(self.get_output_dir(), f"{song_title}.pptx")
                try:
                    prs.save(output_file)
                    self.log(f"\n[Success] Created '{output_file}'.\n")
                    messagebox.showinfo("Success", f"PPT successfully generated!\nSaved as: out/{song_title}.pptx")
                except Exception as e:
                    self.log(f"[Error] Failed to save PPT: {e}")
            else:
                self.log("\n[Error] Lyrics or Sequence cannot be empty.")

if __name__ == "__main__":
    app = LyricsApp()
    app.mainloop()
