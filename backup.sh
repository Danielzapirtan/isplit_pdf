#! /bin/bash

cd /content/drive/MyDrive/
DATE=$(date +6%m%d_%H%M)
PROJECT=split_chapters
zip $PROJECT
mv -f $PROJECT.zip $PROJECT_$DATE.zip
