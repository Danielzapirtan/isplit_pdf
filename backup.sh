#! /bin/bash

cd /content/drive/MyDrive/
DATE=$(date +6%m%d_%H%M)
PROJECT=split_chapters
echo "Compressing ... please wait"
sleep 300
tar -C . -czf ${PROJECT}_$DATE.tar.gz $PROJECT
#rm -rf $PROJECT
echo "Compressed ok"
echo "Open Google Drive and download ${PROJECT}_$DATE.tar.gz"
