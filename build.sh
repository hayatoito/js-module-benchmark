#!/bin/sh
rm -rf out_[234]
python3 gen.py -o out_2 -d 2
python3 gen.py -o out_3 -d 3
python3 gen.py -o out_4 -d 4
