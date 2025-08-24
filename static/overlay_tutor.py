import sys
import requests
import pyttsx3
import pyautogui
import json
import io
import base64
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtCore import Qt, QTimer
from pynput import keyboard

class OverlayTutor(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.engine = pyttsx3.init()
        self.listener = None
        self.setup_hotkey_listener()

    def initUI(self):
        self.setWindowTitle('AI Tutor Overlay')
        self.setGeometry(300, 300, 600, 100)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel('', self)
        self.label.setStyleSheet("QLabel { color : white; font-size: 20px; background-color: rgba(0, 0, 0, 180); padding: 10px; border-radius: 10px; }")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.resize(600, 100)

    def display_and_speak(self, text):
        self.label.setText(text)
        self.show()
        self.engine.say(text)
        self.engine.runAndWait()
        QTimer.singleShot(10000, self.hide)

    def on_press(self, key):
        try:
            # We will use a more specific hotkey for activation
            # For now, let's stick to a simple one for testing.
            if key == keyboard.Key.f10:
                print("F10 pressed! Capturing screen and sending to AI...")
                self.take_screenshot_and_ask("What do you see on this screen? Help me with my task.")
        except AttributeError:
            pass # Ignore special keys
        
    def setup_hotkey_listener(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def take_screenshot_and_ask(self, prompt: str):
        # Taking a screenshot
        screenshot = pyautogui.screenshot()
        
        # Save screenshot to an in-memory buffer
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        
        # Encode the bytes to base64
        base64_image = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        
        # Prepare the payload for the request
        payload = {
            "prompt": prompt,
            "base64_image": base64_image
        }

        try:
            # Send the request
            response = requests.post("http://localhost:8000/screenshot", json=payload, timeout=60)
            response.raise_for_status() 
            
            # Parse the JSON response
            data = response.json()
            ai_response = data.get("ai_answer", "Sorry, no response.")
            
            # Display and speak the AI's response
            self.display_and_speak(ai_response)

        except requests.exceptions.RequestException as e:
            self.display_and_speak(f"Error: Could not connect to the backend. Is it running? {e}")
        except Exception as e:
            self.display_and_speak(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tutor = OverlayTutor()
    tutor.show() 
    sys.exit(app.exec_())