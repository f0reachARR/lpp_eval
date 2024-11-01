#!/bin/bash

set -e

INPUT=submission.bin
FILE_DESC=$(file $INPUT)

if [[ $FILE_DESC == *"Zip archive data"* ]]; then
    echo "Extracting $INPUT"
    unzip -o $INPUT
elif [[ $FILE_DESC == *"gzip compressed data"* ]]; then
    echo "Extracting $INPUT"
    gunzip $INPUT
elif [[ $FILE_DESC == *"7-zip archive data"* ]]; then
    echo "Extracting $INPUT"
    7z x $INPUT
else
    echo "File $INPUT is not a gzip archive"
fi
