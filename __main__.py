import sys
import os

# Dodaj parent direktorij u sys.path da bi radilo i direktno pokretanje
if __name__ == "__main__":
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from asycuda_pro.app import main

if __name__ == "__main__":
    main()
