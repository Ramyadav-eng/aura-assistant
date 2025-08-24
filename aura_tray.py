import pystray
import threading
from mss import mss
from mss.tools import to_png
import requests
from PIL import Image
import logging
import tkinter as tk
import speech_recognition as sr
import queue
import pyperclip

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AURA-Tray")

class AuraUI:
    def __init__(self):
        self.prompt_text = None
        self.response_queue = queue.Queue()
        self.root = None
        self.label = None
        self.entry = None

    def create_window(self, title):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.95)
        self.root.attributes("-topmost", True)
        self.root.config(bg="#21262d", bd=2, relief="groove")
        title_label = tk.Label(self.root, text=title, font=("Segoe UI", 12, "bold"), fg="#58a6ff", bg="#21262d")
        title_label.pack(pady=(10, 5), padx=20, anchor="w")
        self.center_window()

    def center_window(self):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        x = (screen_width // 2) - (self.root.winfo_width() // 2)
        y = 100
        self.root.geometry(f"+{x}+{y}")

    def get_prompt(self):
        self.create_window("AURA")
        self.label = tk.Label(self.root, text="What is your question about the screenshot?", font=("Segoe UI", 10), fg="#c9d1d9", bg="#21262d")
        self.label.pack(pady=5, padx=20, anchor="w")
        self.entry = tk.Entry(self.root, font=("Segoe UI", 10), bg="#161b22", fg="#c9d1d9", insertbackground="white", borderwidth=0, width=50)
        self.entry.pack(pady=10, padx=20, ipady=5)
        self.entry.focus_force()
        def submit():
            self.prompt_text = self.entry.get()
            self.root.destroy()
        def listen_for_voice():
            def recognize():
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    self.label.config(text="Listening...")
                    self.root.update()
                    try:
                        audio = r.listen(source, timeout=5, phrase_time_limit=10)
                        text = r.recognize_google(audio)
                        self.entry.delete(0, tk.END)
                        self.entry.insert(0, text)
                        self.label.config(text="What is your question about the screenshot?")
                    except Exception as e:
                        self.label.config(text=f"Sorry, could not understand. Error: {e}")
            threading.Thread(target=recognize, daemon=True).start()
        button_frame = tk.Frame(self.root, bg="#21262d")
        button_frame.pack(pady=10)
        submit_button = tk.Button(button_frame, text="Submit", font=("Segoe UI", 9, "bold"), bg="#58a6ff", fg="white", borderwidth=0, command=submit)
        submit_button.pack(side=tk.LEFT, padx=5)
        mic_button = tk.Button(button_frame, text="🎤 Speak", font=("Segoe UI", 9, "bold"), bg="#30363d", fg="white", borderwidth=0, command=listen_for_voice)
        mic_button.pack(side=tk.LEFT, padx=5)
        self.root.bind('<Return>', lambda event: submit())
        self.root.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, 'prompt_text', None), self.root.destroy()))
        self.root.mainloop()
        return self.prompt_text

    def show_response(self):
        self.create_window("AURA is thinking...")
        content_label = tk.Label(self.root, text="", font=("Segoe UI", 10), fg="#c9d1d9", bg="#21262d", wraplength=500, justify="left")
        content_label.pack(pady=5, padx=20, anchor="w")
        self.center_window()

        def calculate_display_time(text):
            words_per_minute = 180
            word_count = len(text.split())
            seconds = (word_count / (words_per_minute / 60))
            display_seconds = max(5, min(30, seconds + 4))
            return int(display_seconds * 1000)

        def check_queue():
            try:
                response_text = self.response_queue.get_nowait()
                title_label = self.root.winfo_children()[0]
                title_label.config(text="AURA Response")
                content_label.config(text=response_text)
                def copy_to_clipboard():
                    pyperclip.copy(response_text)
                    copy_button.config(text="Copied!")
                copy_button = tk.Button(self.root, text="Copy", command=copy_to_clipboard, font=("Segoe UI", 9), bg="#30363d", fg="white", borderwidth=0)
                copy_button.pack(pady=(0, 10))
                self.center_window()
                display_time_ms = calculate_display_time(response_text)
                self.root.after(display_time_ms, self.root.destroy)
            except queue.Empty:
                self.root.after(100, check_queue)

        self.root.after(100, check_queue)
        self.root.mainloop()

def capture_and_analyze():
    try:
        with mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img_data = to_png(screenshot.rgb, screenshot.size)
        ui = AuraUI()
        prompt = ui.get_prompt()
        if not prompt:
            logger.info("Analysis canceled.")
            return
        ui_thread = threading.Thread(target=ui.show_response)
        ui_thread.start()
        files = {'file': ('screenshot.png', img_data, 'image/png')}
        data = {'prompt': prompt}
        response = requests.post("http://localhost:8080/screenshot_with_prompt", files=files, data=data, timeout=120)
        if response.status_code == 200:
            ai_response = response.json().get('ai_answer', 'No response received')
            ui.response_queue.put(ai_response)
        else:
            error_msg = f"Backend error: {response.status_code}"
            ui.response_queue.put(error_msg)
    except Exception as e:
        error_msg = f"Capture error: {str(e)}"
        if 'ui' in locals() and ui.root is not None:
            ui.response_queue.put(error_msg)
        else:
            logger.error(error_msg)

if __name__ == "__main__":
    logger.info("Starting AURA System Tray Service...")
    image = Image.new('RGB', (64, 64), (43, 91, 255))
    menu = pystray.Menu(pystray.MenuItem('Analyze Screen', lambda: threading.Thread(target=capture_and_analyze, daemon=True).start(), default=True), pystray.Menu.SEPARATOR, pystray.MenuItem('Exit', lambda icon: icon.stop()))
    icon = pystray.Icon("aura_icon", image, "AURA Assistant (Click to Capture)", menu)
    logger.info("AURA is active. Left-click the icon to capture screen.")
    icon.run()