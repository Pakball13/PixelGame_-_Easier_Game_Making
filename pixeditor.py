import tkinter as tk
from tkinter import filedialog, ttk
import os
import subprocess
import platform
import tempfile
import sys
import io
import re
from pg_interpreter import PGGame

class PixelEditor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PixelEditor")
        self.root.geometry('1200x600')
        
        self.menubar = tk.Menu(self.root)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="New", command=self.new_file)
        self.filemenu.add_command(label="Open", command=self.load)
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Save", command=self.save)
        self.filemenu.add_command(label="Save As", command=self.save_as)
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Exit", command=self.root.quit)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        
        self.editmenu = tk.Menu(self.menubar, tearoff=0)
        self.editmenu.add_command(label="Undo", command=self.undo)
        self.editmenu.add_command(label="Redo", command=self.redo)
        self.menubar.add_cascade(label="Edit", menu=self.editmenu)
        
        self.root.config(menu=self.menubar)
        
        self.root.columnconfigure(0, weight=2)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        
        tk.Label(self.root, text="Code Editor").grid(row=0, column=0, sticky='w')
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky='nsew')
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        self.right_frame = tk.Frame(self.root)
        self.right_frame.grid(row=0, column=1, rowspan=2, sticky='nsew')
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=0)
        self.right_frame.rowconfigure(1, weight=3)
        self.right_frame.rowconfigure(2, weight=0)
        self.right_frame.rowconfigure(3, weight=1)
        
        tk.Label(self.right_frame, text="Preview").grid(row=0, column=0, sticky='w')
        self.embed = tk.Frame(self.right_frame, bg='white', bd=2, relief='raised')
        self.embed.grid(row=1, column=0, sticky='nsew')
        
        tk.Label(self.right_frame, text="Debugger").grid(row=2, column=0, sticky='w')
        self.debugger = tk.Text(self.right_frame, height=10, state='normal')
        self.debugger.grid(row=3, column=0, sticky='nsew')
        
        self.tabs = {}
        self.game = None
        self._after_id = None
        self.debug_stream = None
        self.old_stdout = None
        self.old_stderr = None
        
        self.new_file()
        self.root.mainloop()

    def get_current_text(self):
        if not self.notebook.tabs():
            return None
        current_tab = self.notebook.select()
        return self.tabs.get(current_tab, {}).get('text')

    def get_current_file(self):
        current_tab = self.notebook.select()
        return self.tabs.get(current_tab, {}).get('file')

    def set_current_file(self, filename):
        current_tab = self.notebook.select()
        if current_tab in self.tabs:
            self.tabs[current_tab]['file'] = filename
            self.notebook.tab(current_tab, text=os.path.basename(filename) if filename else "untitled.pg")

    def new_file(self):
        text = tk.Text(self.notebook, width=50, height=40, undo=True)
        tab_id = self.notebook.add(text, text="untitled.pg")
        self.tabs[tab_id] = {'text': text, 'file': None, 'tmp': None, 'preview_scheduled': None, 'highlight_scheduled': None}
        text.tag_configure('keyword', foreground='blue')
        text.tag_configure('number', foreground='orange')
        text.tag_configure('string', foreground='red')
        text.tag_configure('comment', foreground='gray')
        text.bind('<KeyRelease>', self.on_modify)
        self.notebook.select(tab_id)
        self.highlight_text(text)

    def load(self):
        file = filedialog.askopenfilename(filetypes=[("PixelGame Files", "*.pg")])
        if file:
            with open(file, 'r') as f:
                content = f.read()
            text = tk.Text(self.notebook, width=50, height=40, undo=True)
            text.insert(tk.END, content)
            tab_id = self.notebook.add(text, text=os.path.basename(file))
            self.tabs[tab_id] = {'text': text, 'file': file, 'tmp': None, 'preview_scheduled': None, 'highlight_scheduled': None}
            text.tag_configure('keyword', foreground='blue')
            text.tag_configure('number', foreground='orange')
            text.tag_configure('string', foreground='red')
            text.tag_configure('comment', foreground='gray')
            text.bind('<KeyRelease>', self.on_modify)
            self.notebook.select(tab_id)
            self.highlight_text(text)
            self.auto_preview()

    def save(self):
        filename = self.get_current_file()
        text = self.get_current_text()
        if not text or not filename:
            self.save_as()
            return
        with open(filename, 'w') as f:
            f.write(text.get('1.0', tk.END).strip())

    def save_as(self):
        text = self.get_current_text()
        if not text:
            return
        file = filedialog.asksaveasfilename(defaultextension=".pg", filetypes=[("PixelGame Files", "*.pg")])
        if file:
            with open(file, 'w') as f:
                f.write(text.get('1.0', tk.END).strip())
            self.set_current_file(file)

    def undo(self):
        text = self.get_current_text()
        if text:
            try: text.edit_undo()
            except: pass

    def redo(self):
        text = self.get_current_text()
        if text:
            try: text.edit_redo()
            except: pass

    def on_tab_change(self, event):
        self.stop_preview()
        self.debugger.delete('1.0', tk.END)
        self.auto_preview()

    def on_modify(self, event=None):
        text = self.get_current_text()
        if not text:
            return
        current_tab = self.notebook.select()
        if self.tabs[current_tab]['highlight_scheduled']:
            self.root.after_cancel(self.tabs[current_tab]['highlight_scheduled'])
        self.tabs[current_tab]['highlight_scheduled'] = self.root.after(300, lambda t=text: self.highlight_text(t))
        
        if self.tabs[current_tab]['preview_scheduled']:
            self.root.after_cancel(self.tabs[current_tab]['preview_scheduled'])
        self.tabs[current_tab]['preview_scheduled'] = self.root.after(1000, self.auto_preview)

    def highlight_text(self, text_widget):
        content = text_widget.get("1.0", tk.END)
        for tag in ['keyword', 'number', 'string', 'comment']:
            text_widget.tag_remove(tag, "1.0", tk.END)
        
        keyword_pattern = r'\b(create|platform|sprite|at|size|width|height|color|move|left|right|up|down|speed|stop|jump|power|background|gravity|on|off|text|wait|quit|draw|eyes|on|set|x|y|reverse|if|every|frame|touches|key|or|not)\b'
        for match in re.finditer(keyword_pattern, content, re.IGNORECASE):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_widget.tag_add('keyword', start, end)
        
        number_pattern = r'\d+\.?\d*'
        for match in re.finditer(number_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_widget.tag_add('number', start, end)
        
        string_pattern = r'"[^"]*"'
        for match in re.finditer(string_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_widget.tag_add('string', start, end)
        
        comment_pattern = r'#.*'
        for match in re.finditer(comment_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_widget.tag_add('comment', start, end)

    def auto_preview(self):
        self.stop_preview()
        text = self.get_current_text()
        if not text:
            return
        with tempfile.NamedTemporaryFile(suffix='.pg', delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(text.get('1.0', tk.END))
            tmp_filename = tmp.name
        current_tab = self.notebook.select()
        self.tabs[current_tab]['tmp'] = tmp_filename
        
        if platform.system() == "Windows":
            os.environ['SDL_VIDEODRIVER'] = 'windib'
        os.environ['SDL_WINDOWID'] = str(self.embed.winfo_id())
        
        title = os.path.splitext(os.path.basename(self.get_current_file() or 'untitled'))[0].replace('_', ' ').title()
        self.game = PGGame(title=title, embedded=True, tk_root=self.root)
        
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        self.debug_stream = io.StringIO()
        sys.stdout = self.debug_stream
        sys.stderr = self.debug_stream
        self.update_debugger()
        
        self.game.run(tmp_filename)
        
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        self.game = None

    def update_debugger(self):
        if self.debug_stream:
            value = self.debug_stream.getvalue()
            if value:
                self.debugger.insert(tk.END, value)
                self.debugger.see(tk.END)
                self.debug_stream.truncate(0)
                self.debug_stream.seek(0)
        if self.game and self.game.running:
            self._after_id = self.root.after(500, self.update_debugger)

    def stop_preview(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        if self.game:
            self.game.running = False
        current_tab = self.notebook.select()
        if current_tab in self.tabs and self.tabs[current_tab]['tmp']:
            try:
                os.unlink(self.tabs[current_tab]['tmp'])
            except:
                pass
            self.tabs[current_tab]['tmp'] = None
        self.debugger.delete('1.0', tk.END)

    def run_full(self):
        self.save()
        filename = self.get_current_file()
        if filename:
            subprocess.Popen(['python', 'pg_interpreter.py', filename])

if __name__ == "__main__":
    PixelEditor()