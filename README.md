# HydroSafe // Water Quality Intelligence Platform

HydroSafe is a production-level, high-fidelity SaaS dashboard designed to predict water potability and generate compliance reports. The system combines non-linear gradient-boosted decision tree algorithms (**XGBoost**) and game-theoretic local explanation models (**SHAP**) with a rule-based mathematical compliance engine.

---

## Application Previews

### 1. Home Ingestion Overview
![Home Dashboard](assets/home_tab.png)

### 2. Executive Analytics & Telemetry
![Executive Dashboard](assets/dashboard_tab.png)

### 3. Chemical Analysis (SHAP local explanations & WHO compliance matrix)
![Chemical Analysis](assets/analyze_tab.png)

### 4. Smart City Grid Heatmap (16-node status visualizer)
![Smart City Grid](assets/smartcity_tab.png)

### 5. Model Telemetry & Metrics Comparison
![Model Performance](assets/performance_tab.png)

---

## Key SaaS Capabilities
- **Chemical Ingestion Diagnostics:** High-precision input processing for pH, Total Dissolved Solids, Chloramines, Sulfate, and Turbidity.
- **Explainable AI (XAI):** Real-time Chart.js rendering of SHAP contribution weights, detailing how each parameter increases or decreases the likelihood of potability.
- **Smart City Grid Dashboard:** A municipal overview map featuring an interactive 16-node CSS grid heatmap representing active IoT sector telemetry.
- **Live IoT Simulation Stream:** Continuous fluctuation monitoring mode feeding randomized sensor logs through the model at 4-second intervals.
- **Automated Compliance Reports:** High-fidelity ReportLab PDF compiler streaming formatted compliance metrics, WHO violations, and engineering mitigation steps.
- **Dual-Theme Design System:** Translucent, glassmorphic styles with responsive mobile support, transitioning seamlessly between Cyber Dark and Slate Light modes.

---

## Tech Stack
- **Backend Architecture:** Python, Flask WSGI Engine, SQLAlchemy ORM (SQLite/PostgreSQL compatible)
- **Machine Learning Core:** XGBoost, SHAP Explainer, Pandas, NumPy, Scikit-Learn
- **Document Compiling:** ReportLab PDF Generation Library
- **Frontend Core:** Vanilla HTML5, CSS3 Custom Properties (CSS variables), JavaScript (ES6 Modules)
- **Data Visualization:** Chart.js, Lucide Icons

---

## System Architecture

```mermaid
graph TD
    %% Frontend Subsystem
    subgraph Client [Client-Side SPA Dashboard]
        UI[UI View Layer: HTML & Glassmorphic CSS]
        Nav[SPA Tab Navigation Controller]
        Theme[Theme Toggle Controller]
        IoT[IoT Simulation Stream Loop]
        Charts[Telemetry Analytics Charts: Chart.js]
    end

    %% API Layer
    subgraph Backend [Flask Ingestion Backend]
        Routes[API Blueprint Routing Engine]
        Val[Input Validation Service]
        WaterSvc[Water Diagnostics Service]
        Gemini[Gemini Recs API / Fallback Rules Engine]
        PDF[ReportLab PDF Compiler]
    end

    %% Model Subsystem
    subgraph ML [Machine Learning Pipeline]
        Model[XGBoost Classifier Model]
        Shap[SHAP TreeExplainer Engine]
    end

    %% Database Subsystem
    subgraph DB [Database Layer]
        Sqlite[SQLite Development DB]
        Postgres[PostgreSQL Production DB]
    end

    %% Connectors
    UI -->|1. Submit Parameters / JSON| Routes
    IoT -->|1. Simulated Telemetry POST| Routes
    Routes --> Val
    Val -->|2. Validated Vectors| WaterSvc
    WaterSvc -->|3. Run Inference| Model
    WaterSvc -->|4. Explanations| Shap
    WaterSvc -->|5. Recommendation Prompts| Gemini
    WaterSvc -->|6. Log Assessment| DB
    Routes -->|7. PDF Stream GET /api/report/id| PDF
    PDF -->|Query Log| DB
    Routes -->|8. Fetch Aggregates GET /api/location-analytics| DB
    Routes -->|9. JSON Response| UI
    UI --> Charts
    UI -->|Download Report| PDF
```

---

## Machine Learning & Model Evaluation

HydroSafe trains and evaluates 5 distinct classifiers on standard water potability datasets. While other models offer comparable accuracy, **XGBoost** was selected for production due to its fast computation of tree-based Shapley additive contributions, preventing inference latency.

| Classifier Model | Accuracy | Precision | Recall | F1 Score | ROC AUC | Pipeline State |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **XGBoost** | **67.4%** | **64.5%** | **45.2%** | **53.1%** | **68.2%** | **Selected (Production)** |
| Random Forest | 65.8% | 61.2% | 43.8% | 51.0% | 67.5% | Secondary Alternative |
| SVM (RBF Kernel) | 64.2% | 59.8% | 39.5% | 47.6% | 65.1% | Alternative |
| Logistic Regression| 61.5% | 56.4% | 32.1% | 40.9% | 60.8% | Baseline Alternative |
| Decision Tree | 59.1% | 51.3% | 49.8% | 50.5% | 58.7% | Alternative |

---

## Local Development Inception

### 1. Installation & Environment Configuration
Clone the repository and initialize a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database & Model Training Setup
Generate the XGBoost predictive weights, Shap explainer models, and database schema:
```bash
python train_model.py
```
This script evaluates the pipeline and outputs `model_performance_data.json` inside the `app/static/` folder.

### 3. Running the Platform
Start the Flask development server locally:
```bash
python run.py
```
Access the application at `http://127.0.0.1:5000/`.

---

## Production Deployment Instructions

### 1. Database Migration (PostgreSQL Setup)
To transition from SQLite to PostgreSQL in production:
1. Provision a PostgreSQL instance (e.g. Supabase, Render PostgreSQL, or Neon).
2. Configure the database connection string in your environment variables:
   ```env
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```
3. The platform automatically detects the environment variable and binds the engine via SQLAlchemy:
   ```python
   # Inside app/database.py
   DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///water_quality.db")
   # Handles compatibility with older PostgreSQL string variations
   if DATABASE_URL.startswith("postgres://"):
       DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
   ```

### 2. Backend Deployment (Render)
To deploy the Flask API on Render:
1. Connect your Github Repository to Render.
2. Select **Web Service** as the service type.
3. Configure settings:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt && python train_model.py`
   - **Start Command:** `gunicorn -w 4 -b 0.0.0.0:$PORT run:app`
4. Add environment variables under the **Environment** tab:
   - `DATABASE_URL` (your production PostgreSQL connection string)
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = `your_secure_hash_key`
   - `GEMINI_API_KEY` = `your_google_gemini_api_credentials`

### 3. Frontend Deployment (Vercel)
If decoupling the client UI from the backend for a static setup:
1. Ensure the frontend asset fetch URLs point to the Render backend URL (e.g., `https://your-backend.onrender.com`) instead of local paths.
2. Deploy the static directory using Vercel CLI:
   ```bash
   vercel --prod
   ```
3. Alternatively, host the unified Flask template directly on Render (with CSS/JS static endpoints resolved via Flask's static path routes).
