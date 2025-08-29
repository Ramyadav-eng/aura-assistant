import pystray
import threading
import requests
from PIL import Image
import tkinter as tk
from tkinter import ttk
import mss
from mss.tools import to_png
import logging
import queue
import pyperclip
from io import BytesIO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AURA-Tray")

class UIManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.captured_image = None
        self.prompt_text = None
        self.response_text = None
        self.root = None
        self.response_window = None

    def run(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            if self._capture_snip():
                if self._get_prompt():
                    self._process_and_show_response()
        except Exception as e:
            logger.error("Error in UI Manager thread", exc_info=True)
        finally:
            if self.root and self.root.winfo_exists():
                self.root.destroy()

    def _capture_snip(self):
        snip_surface = tk.Toplevel(self.root)
        snip_surface.attributes("-fullscreen", True)
        snip_surface.attributes("-alpha", 0.3)
        snip_surface.attributes("-topmost", True)
        snip_surface.overrideredirect(True)
        snip_surface.config(cursor="crosshair")
        start_x = start_y = 0
        rect = None
        canvas = tk.Canvas(snip_surface, bg="white", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.master.attributes("-alpha", 0.3)

        def on_button_press(event):
            nonlocal start_x, start_y, rect
            start_x, start_y = event.x_root, event.y_root
            rect = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='red', width=2, fill="white")
        
        def on_motion(event):
            canvas.coords(rect, start_x, start_y, event.x_root, event.y_root)

        def on_button_release(event):
            end_x, end_y = event.x_root, event.y_root
            snip_surface.destroy()
            left, right = min(start_x, end_x), max(start_x, end_x)
            top, bottom = min(start_y, end_y), max(start_y, end_y)
            if right - left > 0 and bottom - top > 0:
                monitor = {"top": top, "left": left, "width": right - left, "height": bottom - top}
                with mss.mss() as sct:
                    sct_img = sct.grab(monitor)
                    self.captured_image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        snip_surface.bind("<ButtonPress-1>", on_button_press)
        snip_surface.bind("<B1-Motion>", on_motion)
        snip_surface.bind("<ButtonRelease-1>", on_button_release)
        self.root.wait_window(snip_surface)
        return self.captured_image is not None

    def _get_prompt(self):
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.config(bg="#21262d", bd=2, relief="groove")
        last_click_x = 0; last_click_y = 0
        def on_press(event): nonlocal last_click_x, last_click_y; last_click_x, last_click_y = event.x, event.y
        def on_drag(event): window.geometry(f"+{event.x_root - last_click_x}+{event.y_root - last_click_y}")
        title_frame = tk.Frame(window, bg="#21262d"); title_frame.pack(fill=tk.X, padx=5, pady=2)
        title_frame.bind("<ButtonPress-1>", on_press); title_frame.bind("<B1-Motion>", on_drag)
        tk.Label(title_frame, text="AURA", font=("Segoe UI", 9, "bold"), fg="#58a6ff", bg="#21262d").pack(side=tk.LEFT)
        content_frame = tk.Frame(window, bg="#21262d"); content_frame.pack(padx=15, pady=5)
        tk.Label(content_frame, text="Your question:", font=("Segoe UI", 8), fg="#c9d1d9", bg="#21262d").pack(pady=2, anchor="w")
        entry = tk.Entry(content_frame, font=("Segoe UI", 9), bg="#161b22", fg="#c9d1d9", insertbackground="white", borderwidth=0, width=45)
        entry.pack(pady=5, ipady=4); entry.focus_force()
        def submit(prompt_text): self.prompt_text = prompt_text; window.destroy()
        def cancel(): self.prompt_text = None; window.destroy()
        button_frame = tk.Frame(content_frame, bg="#21262d"); button_frame.pack(pady=5, fill=tk.X)
        tk.Button(button_frame, text="Submit", font=("Segoe UI", 8, "bold"), bg="#58a6ff", fg="white", borderwidth=0, command=lambda: submit(entry.get())).pack(side=tk.LEFT)
        tk.Button(button_frame, text="Cancel", font=("Segoe UI", 8, "bold"), bg="#da3633", fg="white", borderwidth=0, command=cancel).pack(side=tk.RIGHT)
        entry.bind('<Return>', lambda e: submit(entry.get())); window.protocol("WM_DELETE_WINDOW", cancel)
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (window.winfo_width() // 2); y = (window.winfo_screenheight() // 4)
        window.geometry(f"+{x}+{y}")
        self.root.wait_window(window)
        return self.prompt_text is not None

    def _process_and_show_response(self):
        thinking_window = tk.Toplevel(self.root)
        thinking_window.overrideredirect(True)
        thinking_window.attributes("-topmost", True)
        thinking_window.config(bg="#21262d", bd=2, relief="groove")
        tk.Label(thinking_window, text="AURA is thinking...", font=("Segoe UI", 10, "bold"), fg="#58a6ff", bg="#21262d").pack(pady=(10, 5), padx=20)
        progress = ttk.Progressbar(thinking_window, mode='indeterminate', length=200)
        progress.pack(pady=(0, 15), padx=20)
        progress.start(10)
        thinking_window.update_idletasks()
        x = (thinking_window.winfo_screenwidth() // 2) - (thinking_window.winfo_width() // 2)
        y = (thinking_window.winfo_screenheight() // 4)
        thinking_window.geometry(f"+{x}+{y}")

        def update_ui_with_response():
            if self.response_text:
                thinking_window.destroy()
                self._create_response_window()
            else:
                self.root.after(100, update_ui_with_response)

        threading.Thread(target=self._send_request_to_ai, daemon=True).start()
        self.root.after(100, update_ui_with_response)
        self.root.wait_window(thinking_window)

    def _create_response_window(self):
        # Create the response window if it doesn't exist
        if self.response_window is None or not self.response_window.winfo_exists():
            self.response_window = tk.Toplevel(self.root)
            self.response_window.overrideredirect(True)
            self.response_window.attributes("-topmost", True)
            self.response_window.config(bg="#21262d", bd=2, relief="groove")
            
            last_click_x = 0; last_click_y = 0
            def on_press(event): nonlocal last_click_x, last_click_y; last_click_x, last_click_y = event.x, event.y
            def on_drag(event): self.response_window.geometry(f"+{event.x_root - last_click_x}+{event.y_root - last_click_y}")
            
            title_frame = tk.Frame(self.response_window, bg="#21262d"); title_frame.pack(fill=tk.X, padx=5, pady=5)
            title_frame.bind("<ButtonPress-1>", on_press); title_frame.bind("<B1-Motion>", on_drag)
            tk.Label(title_frame, text="AURA Response", font=("Segoe UI", 10, "bold"), fg="#58a6ff", bg="#21262d").pack(side=tk.LEFT)
            
            text_frame = tk.Frame(self.response_window, bg="#161b22"); text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Segoe UI", 10), bg="#161b22", fg="#c9d1d9", relief="flat", height=15)
            scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
            text_widget.config(yscrollcommand=scrollbar.set)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0), pady=10)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            text_widget.insert(tk.END, self.response_text)
            text_widget.config(state=tk.DISABLED)
            
            button_frame = tk.Frame(self.response_window, bg="#21262d"); button_frame.pack(pady=10)
            tk.Button(button_frame, text="Copy", font=("Segoe UI", 9), bg="#30363d", fg="white", borderwidth=0, command=lambda: pyperclip.copy(self.response_text)).pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="Close", font=("Segoe UI", 9), bg="#58a6ff", fg="white", borderwidth=0, command=self.response_window.destroy).pack(side=tk.RIGHT, padx=5)
            
            self.response_window.update_idletasks()
            x = (self.response_window.winfo_screenwidth() // 2) - (600 // 2); y = (self.response_window.winfo_screenheight() // 4)
            self.response_window.geometry(f"600x400+{x}+{y}")
            
            # Make sure the window stays on top
            self.response_window.attributes("-topmost", True)
            
            # Ensure the window is visible
            self.response_window.deiconify()
            
            # Wait for the response window to be closed
            self.root.wait_window(self.response_window)

    def _send_request_to_ai(self):
        try:
            img_byte_arr = BytesIO()
            self.captured_image.save(img_byte_arr, format='PNG')
            img_data = img_byte_arr.getvalue()
            files = {'file': ('screenshot.png', img_data, 'image/png')}
            data = {'prompt': self.prompt_text}
            response = requests.post("http://localhost:8080/screenshot_with_prompt", files=files, data=data, timeout=120)
            self.response_text = response.json().get('ai_answer', 'Error')
        except Exception as e:
            self.response_text = f"Error: {e}"

def start_aura_interaction():
    if any(isinstance(t, UIManager) for t in threading.enumerate()):
        logger.warning("UI interaction already in progress.")
        return
    UIManager().start()

if __name__ == "__main__":
    logger.info("Starting AURA System Tray Service...")
    image = Image.new('RGB', (64, 64), (43, 91, 255))
    menu = pystray.Menu(pystray.MenuItem('Analyze Screen', start_aura_interaction, default=True), pystray.Menu.SEPARATOR, pystray.MenuItem('Exit', lambda icon: icon.stop()))
    icon = pystray.Icon("aura_icon", image, "AURA Assistant", menu)
    icon.run()