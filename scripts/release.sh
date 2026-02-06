#!/bin/bash
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: ./scripts/release.sh <version>"
  echo "Example: ./scripts/release.sh 0.2.0"
  exit 1
fi

REPO="Aosanori/summarizing-movie"
TAP_REPO="Aosanori/homebrew-summarize-movie"

echo "==> Releasing v${VERSION}..."

# Update version in pyproject.toml and __init__.py
sed -i '' "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml
sed -i '' "s/^__version__ = .*/__version__ = \"${VERSION}\"/" summarize_movie/__init__.py

echo "==> Updated version to ${VERSION}"

# Commit, tag, push
git add pyproject.toml summarize_movie/__init__.py
git commit -m "release: v${VERSION}"
git tag "v${VERSION}"
git push origin main "v${VERSION}"

echo "==> Created and pushed tag v${VERSION}"

# Create GitHub release
gh release create "v${VERSION}" --title "v${VERSION}" --generate-notes

echo "==> Created GitHub release v${VERSION}"
echo "==> Waiting for GitHub to generate tarball..."
sleep 5

# Calculate SHA256
TARBALL_URL="https://github.com/${REPO}/archive/refs/tags/v${VERSION}.tar.gz"
SHA256=$(curl -sL "${TARBALL_URL}" | shasum -a 256 | awk '{print $1}')

echo ""
echo "==> SHA256: ${SHA256}"
echo ""
echo "Update the formula in ${TAP_REPO} with:"
echo "  url \"${TARBALL_URL}\""
echo "  sha256 \"${SHA256}\""
echo ""
echo "Or run:"
echo "  cd /path/to/${TAP_REPO}"
echo "  sed -i '' 's|url \".*\"|url \"${TARBALL_URL}\"|' Formula/summarize-movie.rb"
echo "  sed -i '' 's|sha256 \".*\"|sha256 \"${SHA256}\"|' Formula/summarize-movie.rb"
echo "  git add -A && git commit -m 'Update summarize-movie to v${VERSION}' && git push"
