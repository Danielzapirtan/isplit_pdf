#! /bin/bash

cd /content/drive/MyDrive/
DATE=$(date +6%m%d_%H%M)
PROJECT=split_chapters
echo "Compressing ... please wait"
wait
tar -C . -czf ${PROJECT}_$DATE.tar.gz $PROJECT
sleep 20
wait
rm -rf $PROJECT
echo "Compressed ok"
echo "Open Google Drive and download ${PROJECT}_$DATE.tar.gz"
