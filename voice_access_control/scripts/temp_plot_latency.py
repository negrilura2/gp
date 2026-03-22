import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from api.models import VerifyLog
qs = list(VerifyLog.objects.exclude(latency_ms=0).order_by("timestamp")[:500])
os.makedirs("reports/plots/latency", exist_ok=True)
ys = [x.latency_ms for x in qs]
xs = list(range(len(ys)))
plt.figure(figsize=(8, 4))
plt.plot(xs, ys)
plt.xlabel("Sample")
plt.ylabel("Latency (ms)")
plt.title("Verification Latency")
plt.tight_layout()
plt.savefig("reports/plots/latency/latency_curve.png", dpi=160)
