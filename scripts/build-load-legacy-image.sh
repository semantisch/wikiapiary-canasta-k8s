#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${KUBECONFIG_PATH:-/home/vanya/.kube/dobriyai-hosting.yaml}"
NODE_NAME="${NODE_NAME:-dobriyai-hosting-2}"
DEBUG_POD="wikiapiary-image-loader"
IMAGE_REF="${IMAGE_REF:-wikiapiary-legacy:20260501-foreground}"
ARCHIVE_PATH="${ARCHIVE_PATH:-/tmp/wikiapiary-legacy-20260501-foreground.oci.tar}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Building ${IMAGE_REF} from ${repo_root}"
buildah bud \
  --tag "${IMAGE_REF}" \
  --file "${repo_root}/image/legacy-foreground/Containerfile" \
  "${repo_root}"

echo "Exporting OCI archive to ${ARCHIVE_PATH}"
rm -f "${ARCHIVE_PATH}"
buildah push \
  --format oci \
  "${IMAGE_REF}" \
  "oci-archive:${ARCHIVE_PATH}:${IMAGE_REF}"

echo "Creating loader pod on ${NODE_NAME}"
KUBECONFIG="${KUBECONFIG_PATH}" kubectl -n default delete pod "${DEBUG_POD}" --ignore-not-found >/dev/null 2>&1 || true
cat <<EOF | KUBECONFIG="${KUBECONFIG_PATH}" kubectl apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: ${DEBUG_POD}
  namespace: default
spec:
  nodeName: ${NODE_NAME}
  restartPolicy: Never
  hostPID: true
  containers:
    - name: loader
      image: ubuntu
      command: ["sh", "-lc", "sleep 3600"]
      securityContext:
        privileged: true
      volumeMounts:
        - name: host-root
          mountPath: /host
  volumes:
    - name: host-root
      hostPath:
        path: /
        type: Directory
EOF

KUBECONFIG="${KUBECONFIG_PATH}" kubectl -n default wait --for=condition=Ready "pod/${DEBUG_POD}" --timeout=120s >/dev/null

echo "Copying archive into debug pod"
KUBECONFIG="${KUBECONFIG_PATH}" kubectl -n default cp "${ARCHIVE_PATH}" "${DEBUG_POD}:/tmp/wikiapiary-image.tar"

echo "Importing image into host containerd"
KUBECONFIG="${KUBECONFIG_PATH}" kubectl -n default exec "${DEBUG_POD}" -- \
  chroot /host sh -lc "k3s ctr images import /tmp/wikiapiary-image.tar && k3s ctr images ls | grep -F '${IMAGE_REF}'"

echo "Cleaning up debug pod"
KUBECONFIG="${KUBECONFIG_PATH}" kubectl -n default delete pod "${DEBUG_POD}" --ignore-not-found >/dev/null

echo "Loaded ${IMAGE_REF} onto ${NODE_NAME}"
