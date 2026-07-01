#!/bin/bash
set -e

echo "Shutting down staging services..."

railway down --service backend-staging --yes
railway down --service frontend-staging --yes

echo "Done. Staging services stopped."
