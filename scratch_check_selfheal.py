from dotenv import load_dotenv
load_dotenv()
from common.firestore_client import get_firestore_client, COLLECTIONS

db = get_firestore_client()
for d in db.collection(COLLECTIONS.ISSUES).stream():
    v = d.to_dict()
    print(d.id[:8], v.get("asset_id"), v.get("type"), v.get("state"), v.get("severity"),
          "| self_heal:", v.get("self_heal_action"), v.get("self_heal_attempts"))
    if v.get("self_heal_action"):
        print("SELF_HEAL_TRIGGERED")
asset = db.collection(COLLECTIONS.ASSETS).document("ev-1").get().to_dict()
print("ev-1:", asset.get("status"), asset.get("risk_score"))
