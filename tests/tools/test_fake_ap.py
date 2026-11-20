"""tools/fake_ap.py: round 100's fake seed line. The mod plays only on a save linked to a seed."""

import importlib.util
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fake_ap", REPO / "tools" / "fake_ap.py")
fake_ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fake_ap)

work = Path(tempfile.mkdtemp(prefix="ffrap_fake_"))
in_path = work / "ap_in.txt"
assert not fake_ap.has_seed(in_path), "no file yet"
fake_ap.append(in_path, "item", 0, "item", 1, 1, "Potion")
assert not fake_ap.has_seed(in_path), "items alone are no session"
fake_ap.append(in_path, "seed", fake_ap.FAKE_SEED)
assert fake_ap.has_seed(in_path)
assert in_path.read_text(encoding="utf-8").splitlines()[-1] == "seed\tFAKE:0:1"
shutil.rmtree(work)
print("fake_ap seed: ok")
