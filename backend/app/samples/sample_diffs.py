"""
Curated Bundled Sample Diffs demonstrating realistic code review scenarios.
"""

from typing import List
from app.models.schemas import SampleDiff, SeverityLevel


SAMPLE_SQLI_AUTH = SampleDiff(
    id="sample-sqli-auth",
    title="Critical SQL Injection & Hardcoded Secret in Auth Service",
    description="Introduces an authentication endpoint that concatenates raw user input into an SQL query and commits a hardcoded JWT private secret.",
    category_highlight="SECURITY_AND_RELIABILITY",
    expected_severity=SeverityLevel.CRITICAL,
    diff_content="""diff --git a/services/auth_service.py b/services/auth_service.py
index a41bc21..f8910b2 100644
--- a/services/auth_service.py
+++ b/services/auth_service.py
@@ -14,6 +14,24 @@ from database import get_db_connection
 
+JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"
+
 def authenticate_user(email: str, password_hash: str):
     conn = get_db_connection()
     cursor = conn.cursor()
-    cursor.execute("SELECT id, email, role FROM users WHERE email = %s AND password = %s", (email, password_hash))
-    user = cursor.fetchone()
-    return user
+    # Querying user details with direct format
+    raw_query = f"SELECT id, email, role, is_admin FROM users WHERE email = '{email}' AND password = '{password_hash}'"
+    cursor.execute(raw_query)
+    user = cursor.fetchone()
+    if user:
+        token = jwt.encode({"sub": user["id"], "role": user["role"]}, JWT_SECRET_KEY, algorithm="HS256")
+        return {"token": token, "user": user}
+    return None
"""
)

SAMPLE_LOGIC_ASYNC_BUG = SampleDiff(
    id="sample-logic-async-bug",
    title="Payment Gateway Loop Off-by-One & Missing Await Race Condition",
    description="Contains an array index out-of-bounds error in batch iteration and an unawaited async promise in a payment webhook.",
    category_highlight="BUG_OR_LOGIC_ERROR",
    expected_severity=SeverityLevel.CRITICAL,
    diff_content="""diff --git a/payments/processor.py b/payments/processor.py
index b121cc3..e435987 100644
--- a/payments/processor.py
+++ b/payments/processor.py
@@ -42,7 +42,12 @@ class BatchPaymentProcessor:
     def process_settlements(self, settlement_batches: list[dict]):
         processed_records = []
-        for batch in settlement_batches:
-            processed_records.append(self.reconcile(batch))
+        # Process all batches with index tracking
+        for i in range(len(settlement_batches) + 1):
+            batch = settlement_batches[i]
+            status = self.reconcile(batch)
+            processed_records.append({"batch_id": batch["id"], "status": status})
         return processed_records
diff --git a/payments/webhook.ts b/payments/webhook.ts
index c901aa1..d881902 100644
--- a/payments/webhook.ts
+++ b/payments/webhook.ts
@@ -18,6 +18,8 @@ export async function handleStripeWebhook(event: WebhookEvent) {
   if (event.type === "payment_intent.succeeded") {
-    await recordSuccessfulPayment(event.data.object.id);
+    // Dispatch payment confirmation without waiting
+    recordSuccessfulPayment(event.data.object.id);
+    return { status: 200, received: true };
   }
 }
"""
)

SAMPLE_RESOURCE_LEAK = SampleDiff(
    id="sample-resource-leak",
    title="Unclosed File Descriptor Leak & Exception Suppression",
    description="Adds a batch log export that opens files without context managers and suppresses all runtime exceptions with bare except: pass.",
    category_highlight="SECURITY_AND_RELIABILITY",
    expected_severity=SeverityLevel.HIGH,
    diff_content="""diff --git a/analytics/export_worker.py b/analytics/export_worker.py
index e889102..a332190 100644
--- a/analytics/export_worker.py
+++ b/analytics/export_worker.py
@@ -25,9 +25,18 @@ def export_daily_metrics(date_str: str, output_path: str):
-    with open(output_path, "w", encoding="utf-8") as f:
-        json.dump(metrics, f)
+    try:
+        metrics = calculate_system_metrics(date_str)
+        f = open(output_path, "w")
+        for row in metrics:
+            f.write(f"{row['metric']},{row['value']}\\n")
+        # Missing f.close() or context manager
+    except Exception:
+        pass
+    return output_path
"""
)

SAMPLE_UNTESTED_COMPLEXITY = SampleDiff(
    id="sample-untested-complexity",
    title="High-Complexity Financial Calculation Without Test Coverage",
    description="Adds a complex 40-line tax and rebate pricing calculation with deeply nested conditionals, but contains zero corresponding test files.",
    category_highlight="MISSING_TEST_COVERAGE",
    expected_severity=SeverityLevel.HIGH,
    diff_content="""diff --git a/billing/rebate_calculator.py b/billing/rebate_calculator.py
index 1029384..8374651 100644
--- a/billing/rebate_calculator.py
+++ b/billing/rebate_calculator.py
@@ -10,3 +10,42 @@ def calculate_base_price(item_id: str) -> float:
+def calculate_tiered_rebate(customer_tier: str, total_volume: float, is_partner: bool, country_code: str) -> float:
+    discount = 0.0
+    if total_volume > 100000:
+        if is_partner:
+            if customer_tier == "PLATINUM":
+                if country_code in ("US", "CA"):
+                    discount = 0.25
+                else:
+                    discount = 0.22
+            elif customer_tier == "GOLD":
+                discount = 0.18
+            else:
+                discount = 0.12
+        else:
+            if customer_tier == "PLATINUM":
+                discount = 0.15
+            elif customer_tier == "GOLD":
+                discount = 0.10
+            else:
+                discount = 0.05
+    elif total_volume > 50000:
+        if is_partner:
+            if customer_tier == "PLATINUM":
+                discount = 0.12
+            else:
+                discount = 0.08
+        else:
+            discount = 0.04
+    return discount
"""
)

SAMPLE_CLEAN_PR = SampleDiff(
    id="sample-clean-pr",
    title="Clean PR: Production-Ready Rate Limiter With Complete Unit Tests",
    description="Well-engineered in-memory token bucket rate limiter with strict type annotations, thread-safe locks, error handling, and comprehensive unit tests.",
    category_highlight="CODE_QUALITY_AND_MAINTAINABILITY",
    expected_severity=SeverityLevel.INFO,
    diff_content="""diff --git a/security/rate_limiter.py b/security/rate_limiter.py
new file mode 100644
index 0000000..9988112
--- /dev/null
+++ b/security/rate_limiter.py
@@ -0,0 +1,32 @@
+import time
+import threading
+from typing import Dict, Tuple
+
+class TokenBucketRateLimiter:
+    \"\"\"Thread-safe in-memory token bucket rate limiter.\"\"\"
+    
+    def __init__(self, capacity: int, refill_rate_per_sec: float):
+        self.capacity = max(1, capacity)
+        self.refill_rate = max(0.1, refill_rate_per_sec)
+        self._buckets: Dict[str, Tuple[float, float]] = {}
+        self._lock = threading.Lock()
+
+    def allow_request(self, key: str, tokens: int = 1) -> bool:
+        \"\"\"Evaluate whether a request key has available token budget.\"\"\"
+        if not key or tokens <= 0:
+            return False
+        now = time.monotonic()
+        with self._lock:
+            current_tokens, last_refill = self._buckets.get(key, (float(self.capacity), now))
+            elapsed = now - last_refill
+            current_tokens = min(float(self.capacity), current_tokens + (elapsed * self.refill_rate))
+            if current_tokens >= tokens:
+                self._buckets[key] = (current_tokens - tokens, now)
+                return True
+            self._buckets[key] = (current_tokens, now)
+            return False
diff --git a/tests/test_rate_limiter.py b/tests/test_rate_limiter.py
new file mode 100644
index 0000000..3344556
--- /dev/null
+++ b/tests/test_rate_limiter.py
@@ -0,0 +1,18 @@
+import pytest
+from security.rate_limiter import TokenBucketRateLimiter
+
+def test_rate_limiter_allows_under_capacity():
+    limiter = TokenBucketRateLimiter(capacity=5, refill_rate_per_sec=1.0)
+    for _ in range(5):
+        assert limiter.allow_request("client_1") is True
+    assert limiter.allow_request("client_1") is False
+
+def test_rate_limiter_invalid_inputs():
+    limiter = TokenBucketRateLimiter(capacity=10, refill_rate_per_sec=1.0)
+    assert limiter.allow_request("", 1) is False
+    assert limiter.allow_request("client_2", -1) is False
+"""
)

ALL_SAMPLES: List[SampleDiff] = [
    SAMPLE_SQLI_AUTH,
    SAMPLE_LOGIC_ASYNC_BUG,
    SAMPLE_RESOURCE_LEAK,
    SAMPLE_UNTESTED_COMPLEXITY,
    SAMPLE_CLEAN_PR,
]

