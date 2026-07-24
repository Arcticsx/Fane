import sys
from pathlib import Path

# When tests are run from inside the 'tests' directory, add the project root and 'app' to the path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "app"))
