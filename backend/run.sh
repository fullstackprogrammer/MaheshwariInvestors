#!/bin/bash
# Script to run the backend server
cd "$(dirname "$0")"
uvicorn main:app --reload --port 8080 --host 0.0.0.0
