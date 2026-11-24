*** Begin Patch
*** Update File: core/config.py
@@
 def load_config() -> dict:
@@
     _apply_runtime_config(cfg)
     return cfg
+
+
+def _apply_runtime_config_for_test() -> dict:
+    """Return a fresh config with runtime overrides; used by isolated unit tests."""
+    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
+    _apply_runtime_config(cfg)
+    return cfg
*** End Patch