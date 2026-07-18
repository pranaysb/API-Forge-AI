# API Forge AI Benchmark Report

| API | Success | Runtime | Retries | Failure Reason |
|---|---|---|---|---|
| petstore.json | ❌ No | 5.98s | 0 | Job execution failed. One or more endpoints failed. |
| github.json | ❌ No | 0.07s | 0 | HTTP 413: File too large. Maximum allowed size is 10MB. |
| discord.json | ❌ No | 1.96s | 0 | Job execution failed. Integrity error: Traceback (most recent call last):
  File "/var/folders/vc/f7wfsjln21g529vcdfdbk5wc0000gn/T/tmp3dcx7m06/test_script.py", line 4, in <module>
    from apiforge_sdk.client import ApiClient
ModuleNotFoundError: No module named 'apiforge_sdk.client'
 |
| stripe.json | ❌ No | 4.25s | 0 | Job execution failed. Integrity error: Traceback (most recent call last):
  File "/var/folders/vc/f7wfsjln21g529vcdfdbk5wc0000gn/T/tmpw4flg234/test_script.py", line 4, in <module>
    from apiforge_sdk.client import ApiClient
ModuleNotFoundError: No module named 'apiforge_sdk.client'
 |