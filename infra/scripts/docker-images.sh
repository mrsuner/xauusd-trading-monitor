#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-build}"

IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-mrsuner/xauusd-trading-monitor}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE_PLATFORM="${IMAGE_PLATFORM:-}"

SERVICES=(
  "db-migrate:services/db-migrate/Dockerfile"
  "telegram-collector:services/telegram-collector/Dockerfile"
  "rss-collector:services/rss-collector/Dockerfile"
  "normalizer-classifier:services/normalizer-classifier/Dockerfile"
  "event-router:services/event-router/Dockerfile"
  "alert-dispatcher:services/alert-dispatcher/Dockerfile"
  "telegram-channel-publisher:services/telegram-channel-publisher/Dockerfile"
  "x-publisher:services/x-publisher/Dockerfile"
  "dashboard-api:services/dashboard-api/Dockerfile"
  "dashboard-web:apps/dashboard-web/Dockerfile"
)

usage() {
  cat <<EOF
Usage: $0 build|push|build-push

Environment:
  IMAGE_REGISTRY   default: ghcr.io
  IMAGE_NAMESPACE  default: mrsuner/xauusd-trading-monitor
  IMAGE_TAG        default: current git short SHA
  IMAGE_PLATFORM   optional, for example: linux/amd64
EOF
}

image_for() {
  local service="$1"
  printf '%s/%s/%s:%s' "$IMAGE_REGISTRY" "$IMAGE_NAMESPACE" "$service" "$IMAGE_TAG"
}

build_images() {
  for entry in "${SERVICES[@]}"; do
    local service="${entry%%:*}"
    local dockerfile="${entry#*:}"
    local image
    image="$(image_for "$service")"

    echo "Building $image"
    local platform_args=()
    if [[ -n "$IMAGE_PLATFORM" ]]; then
      platform_args=(--platform "$IMAGE_PLATFORM")
    fi

    docker build "${platform_args[@]}" -f "$dockerfile" -t "$image" .
  done
}

buildx_push_images() {
  for entry in "${SERVICES[@]}"; do
    local service="${entry%%:*}"
    local dockerfile="${entry#*:}"
    local image
    image="$(image_for "$service")"

    echo "Building and pushing $image"
    docker buildx build --platform "$IMAGE_PLATFORM" -f "$dockerfile" -t "$image" --push .
  done
}

push_images() {
  for entry in "${SERVICES[@]}"; do
    local service="${entry%%:*}"
    local image
    image="$(image_for "$service")"

    echo "Pushing $image"
    docker push "$image"
  done
}

case "$ACTION" in
  build)
    build_images
    ;;
  push)
    push_images
    ;;
  build-push)
    if [[ -n "$IMAGE_PLATFORM" ]]; then
      buildx_push_images
    else
      build_images
      push_images
    fi
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
