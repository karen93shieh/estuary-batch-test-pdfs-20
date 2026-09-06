"""20-PDF variant of estuary-batch-test-pdfs/generate_pdfs.py (same generator, different
seed, different names, smaller layout). Run from a checkout that has generate_pdfs.py
next to this file:

    python generate_pdfs_20.py <out_dir> <base_url>

Layout: 16 characters, 20 PDFs. Characters 1..3 own 1, 2 and 3 PDFs (so the first
three items of batch_request.json cover the single, dossier+relationships and
dossier+relationships+chronicle shapes), one more character owns 2, the rest own 1.
Character 7 carries a Chinese + Japanese section in its first volume.
"""
import sys

import generate_pdfs as gp

gp.SEED = 20260906
gp.CHAR_COUNT = 16
gp.PDF_COUNT = 20
gp.FIXED_DOC_COUNTS = {1: 1, 2: 2, 3: 3}
gp.EXTRA_DOUBLES = 1
gp.EXTRA_TRIPLES = 0
# different people from the 100-PDF set: rotate the name list so none of the first 16 repeat
gp.FIRST_NAMES = gp.FIRST_NAMES[30:] + gp.FIRST_NAMES[:30]

if __name__ == "__main__":
    gp.main()
