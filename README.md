# Nutrilink AI - Advanced Nutrition & Health Assistant

Nutrilink AI is a comprehensive health management platform that leverages AI to provide nutrition analysis, personalized coaching, and interactive health tracking.

## 🚀 Key Features

- **AI Food Analysis**: Take or upload a photo of your meal to get instant nutritional data (calories, protein, carbs, fats).
- **Personalized Coaching**: An AI nutrition coach that analyzes your history to provide smart meal suggestions.
- **Interactive Chat**: Ask questions about your diet, health goals, and meal history using natural language.
- **Voice Chat**: Support for voice-based interactions for a hands-free experience.
- **Fitness Integration**: Syncs with fitness platforms to correlate meals with activity.
- **Persistent History**: Track your progress over time with a secure cloud-based history log.

---

## 🛠 Tech Stack

- **Frontend**: Vite, React, TypeScript, Tailwind CSS, shadcn/ui.
- **Backend**: FastAPI (Python), Uvicorn.
- **Database**: Firebase (Firestore).
- **AI Engine**: Google Gemini API.

---

## ⚙️ Setup Instructions

Follow these steps to get the project running locally after cloning the repository.

### 1. Backend Setup (FastAPI)

1.  Navigate to the root directory.
2.  Install Python dependencies:
    ```bash
    pip install -r NutriSnap-AI/requirements.txt -r requirements.txt
    ```
3.  Create a `.env` file in the root directory and add your API key:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```
4.  Add your Firebase credentials (see "Database Configuration" below).

### 2. Frontend Setup (React)

1.  Navigate to the `essential-screens` directory:
    ```bash
    cd essential-screens
    ```
2.  Install Node dependencies:
    ```bash
    npm install --legacy-peer-deps
    ```

---

## 🗄 Database Configuration (Firebase)

The project uses Firebase Firestore for persistent data.

1.  Generate a service account key from your [Firebase Console](https://console.firebase.google.com/).
2.  Download the JSON file and rename it to `serviceAccountKey.json`.
3.  Place it in the root directory of this project.

For more details, refer to the [Database Setup Guide](./brain/database_setup_guide.md).

---

## 🏃 Running the Application

To run the full stack, you need to start both the backend and frontend servers.

### Start Backend
From the root directory:
```bash
$env:PYTHONPATH="NutriSnap-AI"; python app.py
```

### Start Frontend
From the `essential-screens` directory:
```bash
npm run dev
```

The application will be accessible at:
- **Frontend**: [http://localhost:8080](http://localhost:8080)
- **Backend API**: [http://localhost:8000](http://localhost:8000)

---

## 📁 Project Structure

```
.
├── NutriSnap-AI/          # Backend source code
│   ├── ai_core/           # AI logic and integrations
│   ├── backend/           # FastAPI routes and models
│   └── requirements.txt   # Backend dependencies
├── essential-screens/     # Frontend source code
│   ├── src/               # React components and pages
│   └── package.json       # Frontend dependencies
├── app.py                 # Root backend entry point
├── serviceAccountKey.json # Firebase credentials (user provided)
└── .env                   # Environment variables (user provided)
```
