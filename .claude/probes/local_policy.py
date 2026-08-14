"""local_policy availability: no adapter dir -> unavailable (never silently base)."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.local_policy import LocalPolicyRewriter

out = {}
# 1. No adapter dir configured -> unavailable
rw = LocalPolicyRewriter(adapter_dir=None)
out["no_dir_unavailable"] = not rw.available()
# 2. Nonexistent dir -> unavailable
rw2 = LocalPolicyRewriter(adapter_dir="/nonexistent/policy")
out["missing_dir_unavailable"] = not rw2.available()
# 3. Base model with use_adapter=False -> availability is dep-only
rw3 = LocalPolicyRewriter(use_adapter=False)
out["base_available_dep_gated"] = isinstance(rw3.available(), bool)
# 4. name changes with use_adapter
out["name_switch"] = LocalPolicyRewriter(use_adapter=False).name == "base-model" and LocalPolicyRewriter().name == "local-policy"
print(json.dumps(out, indent=1))
