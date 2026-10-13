#!/bin/sh
# Kab-board.exe, avec mingw-w64 :  sudo apt install gcc-mingw-w64-x86-64
#   ./lanceur/construire.sh  ->  lanceur/Kab-board.exe
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
cd "$ICI"
x86_64-w64-mingw32-windres -c 65001 kab-board.rc -O coff -o kab-board.res
x86_64-w64-mingw32-gcc -std=c99 -O2 -s -municode -mwindows -Wall -Wextra \
    -o Kab-board.exe kab-board.c kab-board.res
rm -f kab-board.res
ls -l Kab-board.exe | awk '{printf "Kab-board.exe : %d Ko\n", $5/1024}'
