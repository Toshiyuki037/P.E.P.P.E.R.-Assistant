from __future__ import annotations
import re
ACK_ONLY={"ok","okay","alright","all right","got it","thanks","thank you","understood","sounds good","cool"}
LOW_INFORMATION={"you","uh","um","hmm","hm","ah","oh"}
CONTROL_CONFIRMATIONS={"yes","yeah","yep","sure","please","no","nope"}
PHANTOM_ONLY={"so so"}
def normalize(text):
    return " ".join(re.sub(r"[^\w\s']", " ", str(text or "").lower().strip()).split())
def classify_spurious_active_turn(text):
    n=normalize(text)
    if n in CONTROL_CONFIRMATIONS: return False,"control_confirmation"
    if n in ACK_ONLY: return True,"acknowledgement"
    if n in PHANTOM_ONLY: return True,"phantom_transcript"
    if not n or n in LOW_INFORMATION or (len(n.split())==1 and len(n)<=3): return True,"low_information"
    return False,"accepted"
