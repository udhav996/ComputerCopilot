# 🖥️ Computer Copilot  

Computer Copilot is a Python-based **voice assistant with GUI** built using `customtkinter`.  
It can recognize speech, speak back responses, and perform tasks like controlling brightness, opening apps, and answering general questions.  
It also supports **AI-powered responses** via the **Groq API**.  

---

## 🚀 Features  
- 🎙️ Voice command recognition (using `speech_recognition`)  
- 🗣️ Text-to-speech output (using `pyttsx3`)  
- 🖼️ GUI interface built with `customtkinter`  
- 📂 Open apps, music, photos, and videos  
- 🔆 Control screen brightness  
- 🤖 Random fun responses and interactions  
- 🔑 AI Chat via **Groq API**  

---

## 🛠️ Installation & Usage  

Run the following commands step by step in your terminal (PyCharm / VS Code / Command Prompt):  

```bash
# Clone this repository  
git clone https://github.com/udhav996/ComputerCopilot.git  

# Move into the project folder  
cd ComputerCopilot  

# Install dependencies  
pip install -r requirements.txt  

# Run the program  
python computer_copilot.py  


🔐 API Setup (Important for AI Responses)

This project uses the Groq API to answer general questions (like jokes, knowledge queries, etc).

Go to Groq Console
 and create a free account.

Generate your Groq API Key.

In the project folder, create a new file named .env and add this line:

GROQ_API_KEY=your_api_key_here


Save the file. The program will automatically load the key when running.

💡 How the API is Used

System commands (like “open notepad”, “increase brightness”) are handled locally.

If you ask a general knowledge or fun question (like “Tell me a joke” or “What is quantum computing?”), 
the program sends your request to the Groq API and speaks the AI’s response back.