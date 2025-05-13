# 🚴 Indoor Cadence Tracker with Strava Export

A Python script that connects to a Bluetooth Low Energy (BLE) cadence sensor, plots real-time cadence, controls music playback, and saves your indoor cycling workout as a `.tcx` file you can upload to **Strava**.

> Built with help from ChatGPT, who acted like a virtual pair-programming buddy through the whole process. 🙌

---

## 🔧 Features

- ✅ Real-time connection to a BLE cadence sensor
- 📈 Live plot of cadence (RPM) using `matplotlib`
- 🎵 Automatic music control (starts when pedaling, pauses when slowing down)
- 🧠 Intelligent handling of dropped signals and sensor timeouts
- 🛑 Stop button in the UI to end and save your workout
- 📁 Exports a `.tcx` file with multiple timestamped trackpoints for compatibility with **Strava**
- 🕒 Automatically timestamps filenames to avoid overwriting old workouts


---

## 🚴 What You Need

- A BLE cadence sensor (e.g., Garmin, Wahoo)
- A computer with Bluetooth and Python installed
- A wheel circumference (e.g., 2.1 meters) for distance estimation

---

## 📦 Installation

1. **Clone the repo:**

```bash
git clone https://github.com/resilere/bike_to_computer.git

```

2. **Install dependencies:**

```bash
pip install bleak matplotlib keyboard
```

---

## ▶️ Running the Script

1. Replace the `DEVICE_ADDRESS` in the script with your cadence sensor’s Bluetooth address.
2. Run the script:

```bash
python cadence_for_music_interface.py
```

3. Start pedaling! The plot will show live cadence data.
4. Click the **Stop Workout** button to end the session and save the `.tcx` file.

---

## 📤 Uploading to Strava

After your ride, go to [Strava → Upload activity manually](https://www.strava.com/upload/select) and select the `.tcx` file created (it’ll be named like `workout_2025-05-13_17-30-02.tcx`).

---

## ⚠️ Notes

- Strava requires multiple valid **trackpoints with time**. This script handles that.
- GPS is not required for indoor activities.
- `keyboard.send("play/pause media")` might need tweaks depending on your OS.

---

## 🧠 Credits

- Developed with guidance and support from **ChatGPT**.
- Inspired by a love for biking and building personal tools.

---

## 📝 License

MIT License. Use freely, modify widely.
