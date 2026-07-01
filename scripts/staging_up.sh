#!/bin/bash
set -e

echo "Bringing staging services online..."

railway up --service backend-staging --detach
railway up --service frontend-staging --detach

echo "Done."
