import re
import os
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
    # Removes trailing primes (') to find the base key.
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
        
        # If the line is strictly shorter than the minimum threshold (<= 6 to comfortably catch small words), bundle it with the next
        if max_lines == 1 and len(lines[i]) <= MIN_LINE_THRESHOLD and i + 1 < len(lines):
            take_lines = 2
            
        chunk_lines = lines[i:i+take_lines]
        chunks.append('\n'.join(chunk_lines))
        i += len(chunk_lines)
                
    return chunks

# ==========================================
# 2. Core PPT Generator Function
# ==========================================

def append_lyrics_to_ppt(prs, song_title, lyrics_text, sequence_str, compact_mode=False):
    lyrics_dict = parse_lyrics_text(lyrics_text)
    sequence_list = [part.strip() for part in sequence_str.split('-') if part.strip()]
    
    # Check entire song text to assign a fixed lines-per-slide value
    max_lines_per_slide = 4 if compact_mode else 2
    min_lines = 3 if compact_mode else 1
    
    LONG_LINE_THRESHOLD = 18
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
                if len(L) >= LONG_LINE_THRESHOLD:
                    is_long = True
                    break
        if is_long:
            break
            
    if is_long:
        max_lines_per_slide = min_lines
            
    # Find master slide layouts ('Title' & 'Lyrics')
    title_layout = None
    lyrics_layout = None
    
    for layout in prs.slide_layouts:
        if "제목" in layout.name:
            title_layout = layout
        if "가사" in layout.name:
            lyrics_layout = layout
            
    # Fallback indexes
    if title_layout is None:
        title_layout = prs.slide_layouts[2] if len(prs.slide_layouts) > 2 else prs.slide_layouts[0]
    if lyrics_layout is None:
        lyrics_layout = prs.slide_layouts[3] if len(prs.slide_layouts) > 3 else prs.slide_layouts[0]

    # ---- 1. Add Song Title Slide ----
    title_slide = prs.slides.add_slide(title_layout)
    for shape in title_slide.placeholders:
        if shape.has_text_frame:
            shape.text_frame.text = song_title
            break

    # ---- 2. Add Lyrics Slides per Part ----
    for idx, part in enumerate(sequence_list):
        base_part = get_base_key(part)
        
        # Resolve text
        if part in lyrics_dict:
            display_text = lyrics_dict[part]
        elif base_part in lyrics_dict:
            display_text = lyrics_dict[base_part]
        else:
            if part.startswith('(') and part.endswith(')'):
                display_text = part[1:-1].strip()
            else:
                # Skip empty slide for leading 'I' or 'Intro' as Title slide takes its place.
                if idx == 0 and base_part.upper() in ["I", "INTRO"]:
                    continue
                
                # Unregistered parts (like Interlude) are treated as empty lyrics to add a blank slide.
                display_text = "-"
            
        # Chunk text
        chunks = chunk_text(display_text, max_lines_per_slide)
        if not chunks:
            chunks = [""]
            
        # Create slides
        for chunk in chunks:
            slide = prs.slides.add_slide(lyrics_layout)
            
            title_placeholder = None
            body_placeholder = None
            
            for shape in slide.placeholders:
                if shape.has_text_frame:
                    name_lower = shape.name.lower()
                    # Tag as title position if name contains 'title' or '제목'
                    if 'title' in name_lower or '제목' in shape.name:
                        title_placeholder = shape
                    else:
                        if body_placeholder is None:
                            body_placeholder = shape
                            
            # Based on user request: Template text boxes map in reverse, swapping inputs.
            # Place lyrics (chunk) in the Title placeholder area
            if title_placeholder is not None:
                title_placeholder.text_frame.text = chunk
                
            # Place song title in the Body placeholder area
            if body_placeholder is not None:
                body_placeholder.text_frame.text = song_title

# ==========================================
# 3. Batch Processor & Interactive Fallbacks
# ==========================================

def get_manual_lyrics(song_title):
    print(f"Please paste the lyrics for '{song_title}' below.")
    print("(Type 'EOF' on a new line and press Enter when done):")
    print("-" * 40)
    lyrics_lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'EOF':
                break
            lyrics_lines.append(line)
        except EOFError:
            break
    print("-" * 40)
    return '\n'.join(lyrics_lines)

if __name__ == "__main__":
    print("====================================")
    print("   Lyrics PowerPoint Generator")
    print("====================================")
    
    print("\n[Settings]")
    print("1) Standard Mode (1~2 lines per slide)")
    print("2) Compact Mode (3~4 lines per slide)")
    mode_input = input("Select layout mode (1 or 2) [Default: 1]: ").strip()
    compact_mode = (mode_input == "2")
    print("\n")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    TEMPLATE_FILE = os.path.join(script_dir, "template.pptx")
    SEQUENCE_FILE = os.path.join(script_dir, "sequences.txt")
    
    # Initialize a single presentation to embed all lyrics
    if not os.path.exists(TEMPLATE_FILE):
        print(f"[Error] Cannot find template PPTX file '{TEMPLATE_FILE}'.")
        exit(1)
        
    prs = Presentation(TEMPLATE_FILE)
    
    # If sequences.txt exists, do automatic batch generation into ONE file
    if os.path.exists(SEQUENCE_FILE):
        print(f"[Info] Found '{SEQUENCE_FILE}'. Integrating all songs into one PPT...\n")
        
        with open(SEQUENCE_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
        for i in range(0, len(lines), 2):
            song_title = lines[i]
            
            if i + 1 < len(lines):
                sequence_str = lines[i+1]
            else:
                print(f"[Warning] Missing sequence string for '{song_title}'. Skipping...")
                continue
                
            lyrics_file = os.path.join(script_dir, f"{song_title}.txt")
            
            raw_lyrics = ""
            if os.path.exists(lyrics_file):
                print(f"-> Processing '{song_title}'")
                with open(lyrics_file, 'r', encoding='utf-8') as f:
                    raw_lyrics = f.read()
            else:
                print(f"[Warning] '{lyrics_file}' Not Found!")
                raw_lyrics = get_manual_lyrics(song_title)
                
            append_lyrics_to_ppt(prs, song_title, raw_lyrics, sequence_str, compact_mode=compact_mode)
            
        OUTPUT_FILE = os.path.join(script_dir, "integrated_lyrics.pptx")
        prs.save(OUTPUT_FILE)
        print(f"\n[Success] All songs integrated! Created '{OUTPUT_FILE}'.\n")

    # If sequences.txt doesn't exist, gracefully fallback
    else:
        print(f"[Warning] '{SEQUENCE_FILE}' not found in the current folder.")
        print("Falling back to single-song manual mode...\n")
        
        song_title = input("Enter the Song Title: ").strip()
        if not song_title:
            song_title = "Untitled_Song"
            
        sequence_str = input("Enter the Sequence (e.g., I-V1-C-Out): ").strip()
        
        lyrics_file = os.path.join(script_dir, f"{song_title}.txt")
        raw_lyrics = ""
        
        if os.path.exists(lyrics_file):
            print(f"[Success] Found '{lyrics_file}' automatically!")
            with open(lyrics_file, 'r', encoding='utf-8') as f:
                raw_lyrics = f.read()
        else:
            raw_lyrics = get_manual_lyrics(song_title)
            
        if raw_lyrics.strip() and sequence_str.strip():
            append_lyrics_to_ppt(prs, song_title, raw_lyrics, sequence_str, compact_mode=compact_mode)
            OUTPUT_FILE = os.path.join(script_dir, f"{song_title}.pptx")
            prs.save(OUTPUT_FILE)
            print(f"\n[Success] Created '{OUTPUT_FILE}'.\n")
        else:
            print("\n[Error] Lyrics or Sequence cannot be empty.")
