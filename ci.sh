#!/bin/bash
set -euo pipefail

# Variables
REGISTRY="registry.local:30500"
IMAGE_NAME="my_tg_chan_tmdb"

# Get latest tag number from registry
LATEST_TAG=$(curl -s "http://${REGISTRY}/v2/${IMAGE_NAME}/tags/list" | jq -r '.tags[]' | grep -E '^[0-9]+$' | sort -n | tail -1)
if [[ -z "$LATEST_TAG" ]]; then
    NEW_TAG=1
else
    NEW_TAG=$((LATEST_TAG + 1))
fi

# Run tests
echo "Running tests..."
docker run --rm \
  -v "$PWD:/app" \
  python:3.10-slim-buster \
  bash -c "cd /app && pip install -r tmdb/requirements.txt pytest pytest-mock && cd tmdb && PYTHONPATH=${PYTHONPATH:-.} pytest test_dev_tmdb.py -v"

# Build Docker image
echo "Building Docker image..."
cd tmdb && docker build -f dockerfile_tmdb -t "$IMAGE_NAME:$NEW_TAG" . && cd ..

# Tag and push to registry
echo "Pushing to registry..."
docker tag "$IMAGE_NAME:$NEW_TAG" "$REGISTRY/$IMAGE_NAME:$NEW_TAG"
docker push "$REGISTRY/$IMAGE_NAME:$NEW_TAG"

echo "Successfully pushed $REGISTRY/$IMAGE_NAME:$NEW_TAG"


# Clone the amds repo and update manifest
AMDS_REPO="http://gitea.local:30888/gitea_admin/k8s_manifest.git"  # Change to your actual repo
TMP_DIR=$(mktemp -d)
git clone "$AMDS_REPO" "$TMP_DIR"
cp k8s/k8s-manifests.yaml "$TMP_DIR/k8s-manifests.yaml"

# Update k8s manifest with new tag
echo "Updating k8s manifest with tag $NEW_TAG in $TMP_DIR"
sed -i "s/\${TMDB_TAG}/$NEW_TAG/" "$TMP_DIR/k8s-manifests.yaml"


# Commit and push to amds repo

echo "*Pushing updated manifest to amds repo"
cd "$TMP_DIR"
git config --global user.email "ci@example.com"
git config --global user.name "CI Bot"
git add k8s-manifests.yaml
git commit -m "ci: update tmdb to version $NEW_TAG" || echo "No changes to commit"
git push origin main
cd -
rm -rf "$TMP_DIR"

# Commit and push version update to main repo
echo "*Creating git commit for version $NEW_TAG in local branch"
git config --global user.email "ci@example.com"
git config --global user.name "CI Bot"
git add .
git commit -m "ci: update to version $NEW_TAG" || echo "No changes to commit"
# git push origin master

echo "CI pipeline completed successfully"
