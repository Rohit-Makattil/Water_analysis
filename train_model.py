import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix
)
import xgboost as xgb
import joblib

# Load the dataset
data = pd.read_csv("water_potability.csv")

# 1. Data Cleaning (Preserving original logic)
print("Missing values (counts):\n", data.isnull().sum())
data.loc[data["Potability"] == 0] = data[data["Potability"] == 0].fillna(data[data["Potability"] == 0].mean())
data.loc[data["Potability"] == 1] = data[data["Potability"] == 1].fillna(data[data["Potability"] == 1].mean())
print("Missing values after cleaning:\n", data.isnull().sum())

# 2. Feature Engineering (Preserving original logic)
data["ph"] = data["ph"].clip(5, 9)
data["ph_normalized"] = (data["ph"] - 5) / (9 - 5) * 0.1  # Scaled down
data["Sulfate"] = data["Sulfate"].clip(100, 300)  # Raw, clipped
data.replace([np.inf, -np.inf], np.nan, inplace=True)
data.dropna(inplace=True)

# 3. Synthetic Data (Preserving original logic)
np.random.seed(42)
n_synthetic = 50
# Bad cases: Neutral pH, high others
synthetic_bad = pd.DataFrame({
    "ph": np.random.uniform(6.5, 8.5, n_synthetic),
    "Solids": np.random.uniform(12000, 25000, n_synthetic),
    "Chloramines": np.random.uniform(6, 10, n_synthetic),
    "Sulfate": np.random.uniform(200, 300, n_synthetic),
    "Turbidity": np.random.uniform(6, 12, n_synthetic),
    "Potability": [0] * n_synthetic
})
# Good cases: Neutral pH, low others
synthetic_good = pd.DataFrame({
    "ph": np.random.uniform(6.5, 8.5, n_synthetic * 4),  # 200 samples for Potable
    "Solids": np.random.uniform(500, 4000, n_synthetic * 4),
    "Chloramines": np.random.uniform(1, 4, n_synthetic * 4),
    "Sulfate": np.random.uniform(100, 200, n_synthetic * 4),
    "Turbidity": np.random.uniform(1, 2.5, n_synthetic * 4),
    "Potability": [1] * n_synthetic * 4
})

for df in [synthetic_bad, synthetic_good]:
    df["ph"] = df["ph"].clip(5, 9)
    df["ph_normalized"] = (df["ph"] - 5) / (9 - 5) * 0.1
    df["Sulfate"] = df["Sulfate"].clip(100, 300)

data = pd.concat([data, synthetic_bad, synthetic_good], ignore_index=True)

# Define features (X) and target (y)
feature_names = ["ph_normalized", "Solids", "Chloramines", "Sulfate", "Turbidity"]
X = data[feature_names]
y = data["Potability"]

# 4. Compute sample weights (Preserving original logic)
class_weights = {0: len(y) / (2 * (y == 0).sum()), 1: len(y) / (2 * (y == 1).sum())}
sample_weight = np.array([class_weights[yi] * (2.2 if (row["Solids"] > 10000 or row["Chloramines"] > 6 or row["Turbidity"] > 5 or row["Sulfate"] > 250) and yi == 0 else 2.2 if (row["Solids"] < 5000 and row["Chloramines"] < 4 and row["Turbidity"] < 3 and row["Sulfate"] < 200) and yi == 1 else 1) 
                         for yi, (_, row) in zip(y, data.iterrows())])

# 5. Train-Test Split (Preserving original logic)
X_train, X_test, y_train, y_test, sample_weight_train, _ = train_test_split(
    X, y, sample_weight, test_size=0.2, random_state=42
)

# 6. Define and Train the 5 Classifiers
print("\nTraining multiple models for comparison...")

models = {
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
    "Decision Tree": DecisionTreeClassifier(max_depth=5, random_state=42),
    "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
    "SVM": SVC(probability=True, random_state=42),
    "XGBoost": xgb.XGBClassifier(
        n_estimators=450,
        learning_rate=0.02,
        max_depth=4,
        min_child_weight=2,
        subsample=0.9,
        colsample_bytree=0.7,
        random_state=42,
        eval_metric="logloss"
    )
}

metrics_summary = {}
roc_curves = {}

# We'll use sample weights only for XGBoost as in the original model, 
# or other models that support fit parameters where applicable.
for name, clf in models.items():
    print(f"Fitting {name}...")
    if name == "XGBoost":
        clf.fit(X_train, y_train, sample_weight=sample_weight_train)
    else:
        # Fit standard models
        clf.fit(X_train, y_train)
        
    # Predictions
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    
    # Calculate performance metrics
    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    auc = float(roc_auc_score(y_test, y_prob))
    
    metrics_summary[name] = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc": auc
    }
    
    # Calculate ROC curve points and downsample to exactly 50 points to prevent heavy payloads
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    fpr_grid = np.linspace(0.0, 1.0, 50)
    tpr_interp = np.interp(fpr_grid, fpr, tpr)
    
    roc_curves[name] = [{"x": float(x), "y": float(y)} for x, y in zip(fpr_grid, tpr_interp)]

# 7. Extract Specific Confusion Matrix and Feature Importances for selected XGBoost Model
print("\nExtracting detailed statistics for the selected model (XGBoost)...")
xgb_model = models["XGBoost"]
y_pred_xgb = xgb_model.predict(X_test)
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_xgb).ravel()

xgboost_confusion_matrix = {
    "tn": int(tn),
    "fp": int(fp),
    "fn": int(fn),
    "tp": int(tp)
}

friendly_names = {
    "ph_normalized": "pH Level",
    "Solids": "Total Dissolved Solids (TDS)",
    "Chloramines": "Chloramines",
    "Sulfate": "Sulfate",
    "Turbidity": "Turbidity"
}

xgb_importances = xgb_model.feature_importances_
xgboost_feature_importances = [
    {"feature": friendly_names[f], "importance": float(imp)}
    for f, imp in zip(feature_names, xgb_importances)
]

# 8. Save Metrics JSON and final model binary
output_data = {
    "metrics": metrics_summary,
    "roc_curves": roc_curves,
    "xgboost_confusion_matrix": xgboost_confusion_matrix,
    "xgboost_feature_importances": xgboost_feature_importances
}

# Paths to save artifacts
static_dir = os.path.join("app", "static")
os.makedirs(static_dir, exist_ok=True)
json_path = os.path.join(static_dir, "model_performance_data.json")

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4)
    
print(f"Metrics saved to {json_path}")

# Save the final XGBoost model binary to app/ml
model_dir = os.path.join("app", "ml")
os.makedirs(model_dir, exist_ok=True)
model_path = os.path.join(model_dir, "water_quality_model.pkl")
joblib.dump(xgb_model, model_path)
print(f"Selected XGBoost model binary successfully saved to {model_path}")