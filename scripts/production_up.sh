#!/bin/bash
set -e

echo "Bringing production services online..."

railway up --service backend-production --detach
railway up --service frontend-production --detach

echo "Done."
