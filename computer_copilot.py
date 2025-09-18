import customtkinter as ctk
import threading
import speech_recognition as sr
import pyttsx3
import os
import time
import requests
import json
import subprocess
import ctypes
import random
import pyautogui
import sys
import screen_brightness_control as sbc
from PIL import Image, ImageTk
from threading import Event, Lock
import queue
from dotenv import load_dotenv


# ----------------- TTS Engine with Better Configuration -----------------
def create_engine():
    """Create and configure TTS engine"""
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')

    # Better female voice selection
    female_voice = None
    for v in voices:
        voice_name = v.name.lower()
        if any(keyword in voice_name for keyword in ["zira", "hazel", "susan", "female", "woman", "cortana", "eva"]):
            female_voice = v.id
            print(f"Selected female voice: {v.name}")
            break

    if not female_voice:
        for v in voices:
            if "female" in v.name.lower():
                female_voice = v.id
                break
        if not female_voice and len(voices) > 1:
            female_voice = voices[1].id
            print(f"Using fallback voice: {voices[1].name}")

    if female_voice:
        engine.setProperty('voice', female_voice)

    engine.setProperty('rate', 160)
    engine.setProperty('volume', 0.9)

    return engine


# Initialize main engine
engine = create_engine()

# ----------------- Global Variables with Better State Management -----------------
voice_mode = True
listening_active = False
currently_speaking = False
processing_command = False
tts_thread = None
listening_thread = None

# Thread-safe state management
state_lock = Lock()
command_queue = queue.Queue()

# Events for better cancellation control
cancel_tts = Event()
cancel_chat = Event()
shutdown_event = Event()

# ----------------- GUI Setup -----------------
app = ctk.CTk()
app.title("🚀 Computer Copilot")
app.geometry("700x650")

mode_frame = ctk.CTkFrame(app, height=60)
mode_frame.pack(fill="x", padx=15, pady=(15, 5))

mode_label = ctk.CTkLabel(mode_frame, text="Current Mode:", font=("Arial", 14, "bold"))
mode_label.pack(side="left", padx=(10, 5), pady=15)

mode_switch = ctk.CTkSwitch(
    mode_frame,
    text="Voice Mode",
    font=("Arial", 12),
    command=lambda: toggle_mode()
)
mode_switch.pack(side="left", padx=10, pady=15)
mode_switch.select()

mode_status = ctk.CTkLabel(mode_frame, text="🎤 Voice Active", font=("Arial", 12))
mode_status.pack(side="left", padx=10, pady=15)

# Improved stop buttons
stop_chat_button = ctk.CTkButton(
    mode_frame, text="⏹ Stop Chat", font=("Arial", 12, "bold"),
    width=100, fg_color="#e67e22", hover_color="#d35400",
    command=lambda: stop_chat_only()
)
stop_chat_button.pack(side="right", padx=5, pady=15)

stop_all_button = ctk.CTkButton(
    mode_frame, text="⏹ Stop All", font=("Arial", 12, "bold"),
    width=100, fg_color="#e74c3c", hover_color="#c0392b",
    command=lambda: stop_chat_and_speaking()
)
stop_all_button.pack(side="right", padx=5, pady=15)

# Status indicator
status_label = ctk.CTkLabel(mode_frame, text="🟢 Ready", font=("Arial", 10))
status_label.pack(side="right", padx=10, pady=15)

chat_frame = ctk.CTkScrollableFrame(app, width=650, height=350)
chat_frame.pack(pady=10)

canvas = ctk.CTkCanvas(app, width=120, height=120, bg="white", highlightthickness=0)
canvas.pack(pady=10)

# Chat Input Frame
input_frame = ctk.CTkFrame(app, height=80)
input_frame.pack(fill="x", padx=15, pady=(5, 15))

text_entry = ctk.CTkEntry(
    input_frame, placeholder_text="Type your message here...",
    font=("Arial", 12), height=40
)
text_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=20)

send_button = ctk.CTkButton(
    input_frame, text="Send", font=("Arial", 12, "bold"),
    width=80, height=40, command=lambda: send_text_message()
)
send_button.pack(side="right", padx=(5, 10), pady=20)

input_frame.pack_forget()

# ----------------- Load Avatars -----------------
try:
    copilot_img = Image.open("logo.png").resize((40, 40))
    user_img = Image.open("cartoon_face2.png").resize((40, 40))
    copilot_avatar = ImageTk.PhotoImage(copilot_img)
    user_avatar = ImageTk.PhotoImage(user_img)
except:
    copilot_avatar = None
    user_avatar = None

# ----------------- Wave Animation -----------------
pulse_running = False


def update_wave(active):
    global pulse_running
    if active and not pulse_running:
        pulse_running = True
        animate_pulse()
    elif not active:
        pulse_running = False
        canvas.delete("pulse")


def animate_pulse():
    if not pulse_running:
        return
    canvas.delete("pulse")
    size = 50 + (int(time.time() * 10) % 20)
    x, y = 60, 60
    canvas.create_oval(x - size, y - size, x + size, y + size, outline="#4facfe", width=3, tags="pulse")
    canvas.create_oval(x - (size - 10), y - (size - 10), x + (size - 10), y + (size - 10),
                       outline="#00f2fe", width=2, tags="pulse")
    app.after(100, animate_pulse)


# ----------------- Status Update Function -----------------
def update_status(status_text, color="🟢"):
    try:
        status_label.configure(text=f"{color} {status_text}")
        app.update_idletasks()
    except:
        pass


# ----------------- Improved Stop Functions -----------------
def stop_chat_only():
    global processing_command
    print("🛑 STOP CHAT PRESSED")

    with state_lock:
        processing_command = False

    cancel_chat.set()

    # Clear the event after a short delay
    def clear_chat_cancel():
        time.sleep(0.1)
        cancel_chat.clear()

    threading.Thread(target=clear_chat_cancel, daemon=True).start()

    update_wave(False)
    update_status("Chat Stopped", "🟡")

    # Resume listening if in voice mode
    if voice_mode:
        resume_listening()


def stop_chat_and_speaking():
    global processing_command, currently_speaking, engine
    print("🛑 STOP ALL PRESSED")

    with state_lock:
        processing_command = False
        currently_speaking = False

    # Set cancellation events
    cancel_chat.set()
    cancel_tts.set()

    # Stop TTS engine
    try:
        engine.stop()
    except:
        pass

    # Reinitialize engine in separate thread to avoid blocking
    def reinit_engine():
        global engine
        time.sleep(0.2)  # Allow current operations to finish
        try:
            engine = create_engine()
            print("✅ TTS Engine reinitialized")
        except Exception as e:
            print(f"Engine reinit error: {e}")

        # Clear cancellation events
        cancel_tts.clear()
        cancel_chat.clear()

    threading.Thread(target=reinit_engine, daemon=True).start()

    update_wave(False)
    update_status("All Stopped", "🔴")

    # Resume listening if in voice mode
    if voice_mode:
        app.after(300, resume_listening)  # Delay to allow cleanup


def resume_listening():
    """Safely resume listening in voice mode"""
    global listening_active
    if voice_mode and not shutdown_event.is_set():
        with state_lock:
            listening_active = True
        update_status("Listening", "🟢")
        print("✅ Listening resumed")


# ----------------- Mode Toggle -----------------
def toggle_mode():
    global voice_mode, listening_active

    # Stop everything first
    stop_chat_and_speaking()

    voice_mode = mode_switch.get()

    def complete_toggle():
        global listening_active

        if voice_mode:
            mode_switch.configure(text="Voice Mode")
            mode_status.configure(text="🎤 Voice Active")
            input_frame.pack_forget()

            # Resume listening after a brief delay
            time.sleep(0.3)
            listening_active = True
            update_status("Switching to Voice", "🔄")
            speak("Switched to voice mode. I'm ready to listen and respond to your commands.")

        else:
            mode_switch.configure(text="Chat Mode")
            mode_status.configure(text="💬 Chat Active")
            input_frame.pack(fill="x", padx=15, pady=(5, 15))
            listening_active = False
            update_status("Chat Mode", "💬")
            add_bubble("Switched to chat mode. You can now type your messages.", "copilot")
            text_entry.focus()

    # Run in separate thread to prevent blocking
    threading.Thread(target=complete_toggle, daemon=True).start()


# ----------------- Improved Speak Function -----------------
def speak(text):
    global currently_speaking, tts_thread, engine

    print(f"🎯 speak() called: '{text[:50]}...' | voice_mode: {voice_mode}")

    # Always add chat bubble
    threading.Thread(target=lambda: add_bubble(text, "copilot"), daemon=True).start()

    # Only speak in voice mode
    if not voice_mode or shutdown_event.is_set():
        return

    # Stop any existing TTS
    if tts_thread and tts_thread.is_alive():
        cancel_tts.set()
        try:
            engine.stop()
        except:
            pass
        time.sleep(0.1)
        cancel_tts.clear()

    with state_lock:
        currently_speaking = True

    def run_tts():
        global currently_speaking
        try:
            if cancel_tts.is_set() or shutdown_event.is_set():
                return

            update_wave(True)
            update_status("Speaking", "🔊")

            # Clean and prepare text
            clean_text = text.replace("*", "").replace("_", "").strip()

            # Split into sentences for better control
            sentences = [s.strip() + '.' for s in clean_text.split('.') if s.strip()]
            if not sentences:
                sentences = [clean_text]

            # Speak each sentence
            for sentence in sentences:
                if cancel_tts.is_set() or shutdown_event.is_set():
                    break

                engine.say(sentence)

            # Execute speech if not cancelled
            if not cancel_tts.is_set() and not shutdown_event.is_set():
                engine.runAndWait()
            else:
                engine.stop()

            print("✅ TTS completed successfully")

        except Exception as e:
            print(f"❌ TTS Error: {e}")
        finally:
            with state_lock:
                currently_speaking = False
            update_wave(False)

            # Resume listening in voice mode
            if voice_mode and not processing_command and not shutdown_event.is_set():
                resume_listening()
            else:
                update_status("Ready", "🟢")

            print("🔇 TTS thread finished")

    tts_thread = threading.Thread(target=run_tts, daemon=True)
    tts_thread.start()


# ----------------- Chat Functions -----------------
def add_bubble(text, sender="copilot"):
    if shutdown_event.is_set():
        return

    row = ctk.CTkFrame(chat_frame, fg_color="transparent")
    row.pack(anchor="w" if sender == "copilot" else "e", pady=5, padx=5, fill="x")

    if sender == "copilot":
        if copilot_avatar:
            avatar_label = ctk.CTkLabel(row, image=copilot_avatar, text="")
            avatar_label.pack(side="left", padx=5)

        bubble = ctk.CTkLabel(row, text="", font=("Arial", 14), wraplength=400,
                              justify="left", fg_color="#3498db",
                              text_color="white", corner_radius=12, pady=8, padx=12)
        bubble.pack(side="left", padx=5)
    else:
        bubble = ctk.CTkLabel(row, text="", font=("Arial", 14), wraplength=400,
                              justify="right", fg_color="#2ecc71",
                              text_color="white", corner_radius=12, pady=8, padx=12)
        bubble.pack(side="right", padx=5)

        if user_avatar:
            avatar_label = ctk.CTkLabel(row, image=user_avatar, text="")
            avatar_label.pack(side="right", padx=5)

    # Animate text with cancellation support
    words = text.split()

    def animate(i=0):
        if cancel_chat.is_set() or shutdown_event.is_set() or i >= len(words):
            return

        current_text = bubble.cget("text") + (" " if i > 0 else "") + words[i]
        bubble.configure(text=current_text)

        try:
            chat_frame._parent_canvas.yview_moveto(1)
        except:
            pass

        app.after(90, animate, i + 1)

    animate()


def type_user_text(text):
    threading.Thread(target=lambda: add_bubble(text, "user"), daemon=True).start()


def send_text_message():
    user_input = text_entry.get().strip()
    if user_input and not shutdown_event.is_set():
        text_entry.delete(0, ctk.END)
        type_user_text(user_input)
        command_queue.put(user_input.lower())


def on_enter_key(event):
    send_text_message()


text_entry.bind('<Return>', on_enter_key)

# ----------------- Speech Recognition -----------------
recognizer = sr.Recognizer()


def take_command():
    """Improved speech recognition with better error handling"""
    if not voice_mode or not listening_active or currently_speaking or processing_command or shutdown_event.is_set():
        return ""

    try:
        with sr.Microphone() as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            update_wave(True)
            update_status("Listening...", "👂")

            # Listen for audio
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)

            update_wave(False)
            update_status("Processing...", "🔄")

            if shutdown_event.is_set():
                return ""

            # Recognize speech
            command = recognizer.recognize_google(audio).lower()
            print(f"✅ Recognized: '{command}'")

            type_user_text(command)
            return command

    except sr.WaitTimeoutError:
        update_wave(False)
        update_status("Listening", "🟢")
        return ""
    except sr.UnknownValueError:
        update_wave(False)
        update_status("Didn't catch that", "🤔")
        time.sleep(1)
        update_status("Listening", "🟢")
        return ""
    except Exception as e:
        print(f"❌ Recognition error: {e}")
        update_wave(False)
        update_status("Error", "❌")
        time.sleep(1)
        update_status("Listening", "🟢")
        return ""


# ----------------- Groq API -----------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def ask_groq(prompt):
    if shutdown_event.is_set():
        return "Request cancelled."

    if not GROQ_API_KEY:
        return "Groq API key not set."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        elif response.status_code == 429:
            return "Rate limit reached, please wait a moment."
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Failed to contact Groq API: {e}"


# ----------------- Improved Command Handler -----------------
def handle_command(command):
    global listening_active, processing_command

    if not command or shutdown_event.is_set():
        return

    with state_lock:
        processing_command = True
        listening_active = False

    update_status("Processing", "⚡")
    print(f"🎯 Processing command: '{command}'")

    try:
        # Mode switching commands
        if "switch to voice mode" in command or "enable voice mode" in command:
            if not voice_mode:
                mode_switch.select()
                toggle_mode()
            else:
                speak("I'm already in voice mode and ready to talk!")
            return

        elif "switch to chat mode" in command or "enable chat mode" in command or "typing mode" in command:
            if voice_mode:
                mode_switch.deselect()
                toggle_mode()
            else:
                speak("Already in chat mode.")
            return

        # Greeting commands
        elif any(word in command for word in ["hello", "hi", "hey"]):
            speak("Hello Udhav! I'm your sweet assistant Siri. How can I help you today?")

        elif "how are you" in command:
            speak("I'm doing great, thank you for asking! I'm here and ready to help you with anything you need.")

        # System commands
        elif "notepad" in command:
            speak("Opening Notepad for you.")
            os.system("notepad")

        elif "calculator" in command:
            speak("Opening Calculator.")
            subprocess.Popen("calc.exe")

        elif "play music" in command:
            music_path = "music\\sample.mp3"
            if os.path.exists(music_path):
                speak("Playing your music now.")
                os.startfile(music_path)
            else:
                speak("I couldn't find the music file. Please check if it exists.")

        elif "play video" in command:
            video_path = "videos\\sample_video.mp4"
            if os.path.exists(video_path):
                speak("Starting your video.")
                os.startfile(video_path)
            else:
                speak("Video file not found. Please check the file path.")

        elif "increase volume" in command or "volume up" in command:
            speak("Increasing the volume for you.")
            for _ in range(5):
                pyautogui.press("volumeup")

        elif "decrease volume" in command or "volume down" in command:
            speak("Decreasing the volume.")
            for _ in range(5):
                pyautogui.press("volumedown")

        elif "mute" in command:
            speak("Muting the volume.")
            pyautogui.press("volumemute")

        elif "lock system" in command or "lock pc" in command:
            speak("Locking your system now.")
            ctypes.windll.user32.LockWorkStation()

        elif "shutdown" in command:
            speak("Shutting down the system. Goodbye!")
            os.system("shutdown /s /t 1")

        elif "restart" in command:
            speak("Restarting the system.")
            os.system("shutdown /r /t 1")

        elif "open downloads" in command:
            speak("Opening your downloads folder.")
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            os.startfile(downloads_path)

        elif "open google" in command:
            speak("Opening Google for you.")
            os.system("start https://www.google.com")

        elif "open youtube" in command:
            speak("Opening YouTube.")
            os.system("start https://www.youtube.com")

        elif "increase brightness" in command:
            try:
                current = sbc.get_brightness()[0]
                sbc.set_brightness(min(current + 20, 100))
                speak("Brightness increased.")
            except:
                speak("Sorry, I couldn't change the brightness.")

        elif "decrease brightness" in command:
            try:
                current = sbc.get_brightness()[0]
                sbc.set_brightness(max(current - 20, 0))
                speak("Brightness decreased.")
            except:
                speak("Sorry, I couldn't change the brightness.")

        elif "change wallpaper" in command:
            wallpaper_folder = "wallpapers"
            try:
                wallpapers = [os.path.join(wallpaper_folder, f) for f in os.listdir(wallpaper_folder)
                              if f.endswith((".jpg", ".png"))]
                if wallpapers:
                    chosen = random.choice(wallpapers)
                    ctypes.windll.user32.SystemParametersInfoW(20, 0, os.path.abspath(chosen), 3)
                    speak("I've changed your wallpaper!")
                else:
                    speak("I couldn't find any wallpaper images.")
            except:
                speak("Sorry, I couldn't change the wallpaper.")

        elif "exit" in command or "quit" in command or "goodbye" in command:
            speak("Goodbye Udhav! It was nice talking with you. Have a great day!")
            shutdown_event.set()
            time.sleep(2)  # Let the goodbye message finish
            app.quit()
            return

        # Fallback to Groq API
        else:
            if not shutdown_event.is_set():
                speak("Let me think about that for you.")
                if not cancel_chat.is_set() and not shutdown_event.is_set():
                    answer = ask_groq(command)
                    if answer and not shutdown_event.is_set():
                        speak(answer)

    except Exception as e:
        print(f"❌ Error in handle_command: {e}")
        if not shutdown_event.is_set():
            speak("Sorry, I encountered an error while processing your request.")

    finally:
        with state_lock:
            processing_command = False

        # Resume listening in voice mode after processing
        if voice_mode and not shutdown_event.is_set():
            # Small delay to ensure TTS starts if needed
            def delayed_resume():
                time.sleep(0.5)
                if not currently_speaking and not shutdown_event.is_set():
                    resume_listening()

            threading.Thread(target=delayed_resume, daemon=True).start()


# ----------------- Robust Listening Loop -----------------
def listening_loop():
    """Main listening loop with improved error handling and recovery"""
    global listening_active
    print("🎧 Listening loop started")

    consecutive_errors = 0
    max_consecutive_errors = 5

    while not shutdown_event.is_set():
        try:
            # Process any queued commands from chat mode
            if not command_queue.empty():
                command = command_queue.get_nowait()
                threading.Thread(target=lambda: handle_command(command), daemon=True).start()
                continue

            # Voice mode listening logic
            if voice_mode and not processing_command and not currently_speaking:
                # Auto-enable listening if it's disabled (failsafe)
                if not listening_active:
                    print("🔄 Auto-enabling listening (failsafe)")
                    with state_lock:
                        listening_active = True
                    update_status("Auto-resumed", "🔄")

                # Try to get voice command
                if listening_active:
                    command = take_command()
                    if command and not shutdown_event.is_set():
                        # Disable listening while processing
                        with state_lock:
                            listening_active = False

                        # Process command in separate thread
                        threading.Thread(target=lambda: handle_command(command), daemon=True).start()
                        consecutive_errors = 0  # Reset error counter on success

            else:
                # Not in voice mode or busy - just wait
                time.sleep(0.5)

            # Reset error counter if we get here without exception
            consecutive_errors = 0

        except Exception as e:
            print(f"❌ Listening loop error: {e}")
            consecutive_errors += 1

            # If too many consecutive errors, take a longer break
            if consecutive_errors >= max_consecutive_errors:
                print(f"⚠️ Too many consecutive errors ({consecutive_errors}), taking longer break")
                update_status("Error Recovery", "🔧")
                time.sleep(5)
                consecutive_errors = 0

                # Try to recover by resetting listening state
                if voice_mode and not shutdown_event.is_set():
                    with state_lock:
                        listening_active = True
                    update_status("Recovered", "✅")
            else:
                time.sleep(1)

    print("🛑 Listening loop ended")


# ----------------- Startup Function -----------------
def start_after_welcome():
    global listening_active, listening_thread
    print("🚀 Starting Computer Copilot...")

    # Clear all events
    cancel_tts.clear()
    cancel_chat.clear()
    shutdown_event.clear()

    # Enable listening
    with state_lock:
        listening_active = True

    update_status("Starting...", "🚀")

    # Welcome message
    speak(
        "Hi Udhav! I'm your personal assistant.I'm ready to help you with anything you need")

    # Start the main listening loop
    listening_thread = threading.Thread(target=listening_loop, daemon=True)
    listening_thread.start()


# ----------------- Application Shutdown Handler -----------------
def on_closing():
    print("🛑 Application closing...")
    shutdown_event.set()

    try:
        engine.stop()
    except:
        pass

    app.quit()


app.protocol("WM_DELETE_WINDOW", on_closing)

# ----------------- Start Application -----------------
print("🎯 Initializing Computer Copilot...")
app.after(1000, start_after_welcome)
app.mainloop()