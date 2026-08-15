import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _strip_meta_closers

out = {}
# trailing pure sign-off removed
t1 = "The fix works now. I hope this helps!"
out["trailing_removed"] = _strip_meta_closers(t1).strip().endswith("now.")
out["kept_content"] = "The fix works now." in _strip_meta_closers(t1)
# mid-document instruction KEPT
t2 = "Let me know if the build fails. I will check the logs."
out["mid_kept"] = "Let me know" in _strip_meta_closers(t2)
# sign-off with real content kept (17-word conclusion case)
t3 = "I hope this helps to explain why we might not have high resolution color cameras on some space probes and satellites."
out["content_signoff_kept"] = _strip_meta_closers(t3) == t3
print(json.dumps(out, indent=1))
