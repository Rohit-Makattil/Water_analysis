import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import xgboost as xgb
import joblib

# Load the dataset
data = pd.read_csv("water_potability.csv")

# 1. Data Cleaning
print("Missing values (counts):\n", data.isnull().sum())
data.loc[data["Potability"] == 0] = data[data["Potability"] == 0].fillna(data[data["Potability"] == 0].mean())
data.loc[data["Potability"] == 1] = data[data["Potability"] == 1].fillna(data[data["Potability"] == 1].mean())
print("Missing values after cleaning:\n", data.isnull().sum())

# 2. Feature Engineering
data["ph"] = data["ph"].clip(5, 9)
data["ph_normalized"] = (data["ph"] - 5) / (9 - 5) * 0.1  # Scaled down
data["Sulfate"] = data["Sulfate"].clip(100, 300)  # Raw, clipped
data.replace([np.inf, -np.inf], np.nan, inplace=True)
data.dropna(inplace=True)

# 3. Synthetic Data
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

# Check class distribution
print("Class distribution:\n", data["Potability"].value_counts(normalize=True).to_string())

# Define features (X) and target (y)
feature_names = ["ph_normalized", "Solids", "Chloramines", "Sulfate", "Turbidity"]
X = data[feature_names]
y = data["Potability"]

# 4. Compute sample weights
class_weights = {0: len(y) / (2 * (y == 0).sum()), 1: len(y) / (2 * (y == 1).sum())}
sample_weight = np.array([class_weights[yi] * (2.2 if (row["Solids"] > 10000 or row["Chloramines"] > 6 or row["Turbidity"] > 5 or row["Sulfate"] > 250) and yi == 0 else 2.2 if (row["Solids"] < 5000 and row["Chloramines"] < 4 and row["Turbidity"] < 3 and row["Sulfate"] < 200) and yi == 1 else 1) 
                         for yi, (_, row) in zip(y, data.iterrows())])

# 5. Train-Test Split
X_train, X_test, y_train, y_test, sample_weight_train, _ = train_test_split(
    X, y, sample_weight, test_size=0.2, random_state=42
)

# 6. Train XGBoost
print("Training XGBoost...")
model_xgb = xgb.XGBClassifier(
    n_estimators=450,
    learning_rate=0.02,
    max_depth=4,
    min_child_weight=2,
    subsample=0.9,
    colsample_bytree=0.7,
    random_state=42,
    eval_metric="logloss"
)
model_xgb.fit(X_train, y_train, sample_weight=sample_weight_train)

# Evaluate
train_score_xgb = model_xgb.score(X_train, y_train)
test_score_xgb = model_xgb.score(X_test, y_test)
print(f"XGBoost Training Accuracy: {train_score_xgb:.4f}")
print(f"XGBoost Testing Accuracy: {test_score_xgb:.4f}")

# Feature Importance
print("\nXGBoost Feature Importance:")
for name, imp in zip(feature_names, model_xgb.feature_importances_):
    print(f"{name}: {imp:.4f}")

# 7. Save model
print(f"\nSaving model with test accuracy: {test_score_xgb:.4f}")
joblib.dump(model_xgb, "water_quality_model.pkl")
print("Model saved successfully!")

# 8. Test predictions
good_input = pd.DataFrame([[7.2, 500, 2.5, 200, 1.5]], columns=feature_names)
bad_input = pd.DataFrame([[4.5, 15000, 7.0, 300, 8.0]], columns=feature_names)
good_input["ph_normalized"] = (good_input["ph_normalized"] - 5) / (9 - 5) * 0.1
bad_input["ph_normalized"] = (bad_input["ph_normalized"] - 5) / (9 - 5) * 0.1

print("\nSample Predictions:")
print(f"Good Water: {'Potable' if model_xgb.predict(good_input)[0] == 1 else 'Not Potable'}")
print(f"Bad Water: {'Potable' if model_xgb.predict(bad_input)[0] == 1 else 'Not Potable'}")