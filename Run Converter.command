#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$DIR"

# Run the Python script
python3 jsontoxml.py

# Keep the terminal window open if there's an error
read -p "Press [Enter] key to close..." 