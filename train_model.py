import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sqlalchemy import create_engine
import joblib
import yaml

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

engine = create_engine(config['database']['url'])

df = pd.read_sql("""
    SELECT status, protocol, reliability,
           network_load, rxload, input_errors, label
    FROM interface_logs
    WHERE label IS NOT NULL
      AND status != 'admin_down'
""", engine)

print(f"✅ โหลดข้อมูลสำเร็จ: {len(df)} rows")
print(df['label'].value_counts())

df['status_num']   = (df['status']   == 'up').astype(int)
df['protocol_num'] = (df['protocol'] == 'up').astype(int)

X = df[['status_num', 'protocol_num', 'reliability',
         'network_load', 'rxload', 'input_errors']]
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"\n📊 Train: {len(X_train)} rows | Test: {len(X_test)} rows")

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
print("\n✅ เทรนเสร็จแล้ว!")

y_pred = model.predict(X_test)
print("\n📈 Classification Report:")
print(classification_report(y_test, y_pred))

print("🔢 Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))

features = ['status_num', 'protocol_num', 'reliability',
            'network_load', 'rxload', 'input_errors']
importance = pd.Series(model.feature_importances_, index=features)
print("\n⭐ Feature Importance:")
print(importance.sort_values(ascending=False))

joblib.dump(model, config['model']['path'])
print(f"\n💾 บันทึก model เป็น {config['model']['path']} สำเร็จ!")