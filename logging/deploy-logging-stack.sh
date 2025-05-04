# 1. Add Helm repo and update
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# 2. Create namespace for monitoring
kubectl create namespace monitoring

# 3. Install Loki (expose via NodePort 31000)
helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=false \
  --set promtail.enabled=false \
  --set loki.service.type=NodePort \
  --set loki.service.nodePort=31000

# 4. Install Promtail to collect logs and push to Loki
helm upgrade --install promtail grafana/promtail \
  --namespace monitoring \
  --set 'config.clients[0].url=http://loki.monitoring.svc.cluster.local:3100/loki/api/v1/push'

# 5. Create Grafana values.yaml with NodePort and persistence
cat <<EOF > grafana-values.yaml
adminUser: admin
adminPassword: admin

service:
  type: NodePort
  nodePort: 32000

persistence:
  enabled: true
  storageClassName: ""
  accessModes:
    - ReadWriteOnce
  size: 1Gi

datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Loki
        type: loki
        access: proxy
        url: http://loki.monitoring.svc.cluster.local:3100
        isDefault: true
EOF

# 6. Install Grafana with NodePort 32000 and persistent volume
helm upgrade --install grafana grafana/grafana \
  --namespace monitoring \
  --values grafana-values.yaml
