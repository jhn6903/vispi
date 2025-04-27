# Pi Audio Visualizers

A collection of Python scripts for Raspberry Pi that react to audio input, drawing bar charts, waveforms, text animations, and more—either in the terminal or on small attached displays.

---

## 📋 Table of Contents
1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Dependencies](#dependencies)
7. [Project Structure](#project-structure)
8. [Contributing](#contributing)
9. [License](#license)

---

## ✨ Features
- Real‑time FFT bar charts and waveforms
- ASCII and Unicode character visualizations
- MIDI‑triggered effects
- Support for onboard audio input or USB soundcards (RCA/3.5mm)
- Multiple demo scripts for different styles and modes

---

## 🛠 Prerequisites
- **Hardware**: Raspberry Pi (3, 4, Zero W) with audio input (built‑in or USB interface) and optional small display (OLED/LCD)
- **OS**: Raspberry Pi OS (32‑bit or 64‑bit)
- **Python**: 3.7 or newer
- **PortAudio**: `brew install portaudio`

---

## 🚀 Installation
1. **Clone the repo**
    ```bash
    git clone git@github.com:jhn6903/vispi.git
    cd vispi
    ```

2. **Set up a virtual environment** (recommended)
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install Python dependencies**
    ```bash
    pip install -r requirements.txt
    ```

---

## 🔧 Configuration
1. **ALSA Audio Device**: Identify your input device index:
    ```bash
    arecord -l
    ```
    Then pass `--device INDEX` to scripts that require it.

2. **Command‑line Tools**: Some visualizers may require additional packages or system modules:
    ```bash
    sudo apt update && sudo apt install python3-pyaudio
    sudo modprobe snd_bcm2835
    ```

3. **MIDI Controllers**: If using MIDI, install:
    ```bash
    sudo apt install python3-rtmidi
    ```

---

## Simulator Setup (macOS)
    `brew install sox`
    Install [BlackHole](https://existential.audio/blackhole/) 
    [Setup Multi-Output Device in BlackHole](https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device)
    run simtest.py to test

## ▶️ Usage
Each script in `/` has its own header with run instructions. Example:
```bash
python visualizer_hud.py --device 1 --bars 8 --smooth 0.7
```

- **Common flags**:
  - `--device N` : ALSA capture device ID
  - `--bars N` : Number of FFT bars
  - `--smooth F` : Smoothing factor (0–1)

---

## 📂 Project Structure
```
vispi/
├── README.md
├── requirements.txt
├── .gitignore
├── visualizer_hud.py
├── console_demo.py
├── fftv_pat.py
├── launch_random.py
├── notusing/      # old or experimental scripts
└── visualizers_midi/  # MIDI demos (avoid large media here)
```

---

## 🤝 Contributing
1. Create a feature branch:
   ```bash
   git checkout -b feature/my-cool-effect
   ```
2. Commit changes with clear, descriptive messages:
   ```bash
   git commit -m "Add glitch effect mode"
   ```
3. Push and open a Pull Request on GitHub.

Please keep commits small and focused. Follow the [branch naming convention](https://www.git-scm.com/book/en/v2/Git-Branching-Branch-Naming) `feature/...` or `fix/...`.

---

## 📄 License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

