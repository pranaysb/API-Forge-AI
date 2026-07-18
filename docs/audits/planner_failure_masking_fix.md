# Planner Failure Masking Fix

## Previous Behavior
When the `planner_node` encountered an unrecoverable exception (such as token limit exhaustion for massive API specs like Discord and Stripe), it returned an empty `sdk_files` payload and populated the state's `errors` array. The LangGraph engine correctly observed the errors and aborted execution. However, `stream.py` unconditionally executed the "Final SDK Quality Gate" using the empty payload. This caused the local testing sandbox to throw a `ModuleNotFoundError` when it tried to import the empty `apiforge_sdk`. The frontend thus received a misleading integrity error masking the original context limit exception.

## New Behavior
Execution in `stream.py` now detects if `errors` exist or if `sdk_files` is entirely empty before running the Final SDK Quality Gate. If errors are present, the job fails immediately and surfaces the original `Planner error` directly to the client via Server-Sent Events (SSE). The sandbox is bypassed, preventing the synthetic `ModuleNotFoundError`. Successful runs are entirely unaffected.

## Exact Code Changes

**File:** `backend/app/api/stream.py`
**Lines Modified:** ~161-164

```python
@@ -160,6 +160,28 @@
                 yield f"data: {json.dumps({'status': 'complete', 'message': 'Job execution failed due to recursion limit'})}\n\n"
                 return
                 
+            # Check for early termination or planner errors
+            graph_errors = full_state.get("errors", [])
+            sdk_files = full_state.get("sdk_files", {})
+            
+            if graph_errors:
+                job.status = "FAILED"
+                job.completed_at = datetime.utcnow()
+                db.commit()
+                # Surface the first error to the client
+                error_msg = graph_errors[0]
+                yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
+                yield f"data: {json.dumps({'status': 'complete', 'message': f'Job execution failed: {error_msg}'})}\n\n"
+                return
+                
+            if not sdk_files:
+                job.status = "FAILED"
+                job.completed_at = datetime.utcnow()
+                db.commit()
+                yield f"data: {json.dumps({'status': 'error', 'message': 'SDK files were not generated'})}\n\n"
+                yield f"data: {json.dumps({'status': 'complete', 'message': 'Job execution failed: SDK generation aborted'})}\n\n"
+                return
+
             # Final SDK Quality Gate
             test_script = \"\"\"import httpx
```

## SSE Payload Comparison

### Before (Masked Error)
```json
data: {"status": "complete", "message": "Job execution failed. Integrity error: Traceback (most recent call last):\n  File \"/var/folders/.../test_script.py\", line 4, in <module>\n    from apiforge_sdk.client import ApiClient\nModuleNotFoundError: No module named 'apiforge_sdk.client'\n"}
```

### After (Surfaced Original Error)
```json
data: {"status": "error", "message": "Planner error: ReliabilityManager exhausted all keys and models due to repeated errors."}

data: {"status": "complete", "message": "Job execution failed: Planner error: ReliabilityManager exhausted all keys and models due to repeated errors."}
```
