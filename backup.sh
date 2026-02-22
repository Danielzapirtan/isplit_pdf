#! /bin/bash

cd /content/drive/MyDrive/
DATE=$(date +6%m%d_%H%M)
PROJECT=split_chapters
echo "Compressing ... please wait"
sleep 20
tar -C . -czf $PROJECT_$DATE.gz $PROJECT
sleep 20
rm $PROJECT
