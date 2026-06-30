# Skill: Virtual Environment Setup

Read this file before running any Python script or installing any dependency.

---

## 1. Purpose

All Python scripts run inside a virtual environment at `venv/` in the project root. Never install packages globally.

---

## 2. Creating the Virtual Environment

If `venv/` does not exist:

```
python3 -m venv venv
```

---

## 3. Activating

```
source venv/bin/activate
```

This project is developed on macOS. Windows activation (`venv\Scripts\activate`) is not the target platform.

---

## 4. Installing Dependencies

After activating:

```
pip install httpx python-dotenv pandas rapidfuzz anthropic
```

---

## 5. Verifying Activation

The shell prompt will show `(venv)` when active. If it is not shown, activate before proceeding.

---

## 6. .gitignore

`venv/` must be listed in `.gitignore`. If `.gitignore` does not exist or does not contain `venv/`, add it before doing anything else.

---

## 7. Non-Obvious Rules

- Never run `pip install` without activating first.
- Never commit `venv/` to git.
- If a script raises `ModuleNotFoundError`, verify the virtual environment is active before debugging further.
