#! /bin/bash

cd /content/drive/MyDrive/
DATE=$(date +6%m%d_%H%M)
PROJECT=split_chapters
echo "Compressing ... please wait"
wait
tar -C . -czf ${PROJECT}_$DATE.gz $PROJECT
sleep 20
rm $PROJECT
