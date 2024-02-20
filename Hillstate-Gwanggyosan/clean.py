import os
import shutil

CURPATH = os.path.dirname(os.path.abspath(__file__))
for (p, d, files) in os.walk(CURPATH):
    if '__pycache__' in p:
        shutil.rmtree(p, ignore_errors=False)