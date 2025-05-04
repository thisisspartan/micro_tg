# Movie Poster Telegram Bot (Kubernetes Deployment)

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)

A sophisticated microservices architecture that automatically fetches movie posters from TMDB API and publishes them to Telegram, built with Kubernetes, Redis, and Python.

## 🚀 Key Features

- **Automated Pipeline**: Fetches movie data from TMDB API every 40 seconds
- **Telegram Integration**: Publishes posters with ratings to configured Telegram channel
- **Kubernetes Deployment**: Full CI/CD pipeline with ArgoCD for GitOps
- **Observability**: Integrated with Loki, Promtail and Grafana for logging
- **Resilient Architecture**: Health checks, retries, and proper error handling

## 🛠️ Technical Stack

| Component       | Technology |
|-----------------|------------|
| Orchestration   | Kubernetes |
| CI/CD           | ArgoCD, GitOps |
| Cache           | Redis |
| Monitoring      | Loki, Promtail, Grafana |
| Language        | Python 3.10 |
| Networking      | SOCKS5 Tunnels |

## 📦 System Architecture

```mermaid
graph TD
    subgraph Kubernetes Cluster
        subgraph GitOps
            Gitea[(Gitea Repo)] -->|Manifests| ArgoCD
            ArgoCD -->|Sync| AppNamespace
        end
        
        subgraph Monitoring
            Promtail -->|Logs| Loki
            Grafana -->|Visualize| Loki
        end
        
        subgraph AppNamespace
            TMDB[TMDB Service] -->|Store| Redis[(Redis)]
            Redis --> Telegram[Telegram Bot]
            Telegram -->|Publish| Channel[Telegram Channel]
            Tunnel[SSH Tunnel] --> TMDB
        end
    end
    
    External[TMDB API] -->|Fetch Data| TMDB
    Channel -->|User Interaction| EndUser[End Users]
    
    style Kubernetes Cluster fill:#f5f5f5,stroke:#333,stroke-width:2px
    style GitOps fill:#e6f7ff,stroke:#1890ff
    style Monitoring fill:#fff7e6,stroke:#faad14
    style AppNamespace fill:#f6ffed,stroke:#52c41a
```

## 🔧 Installation

### Prerequisites
- Kubernetes cluster
- Redis
- Telegram Bot Token
- TMDB API credentials

```bash
# Clone the repository
git clone https://your-repository-url.git
cd my_tg_chan

# Deploy to Kubernetes
kubectl apply -f k8s/k8s-manifests.yaml
```

## 📊 Metrics & Monitoring

The system includes comprehensive logging with:
- Structured JSON logs
- Trace IDs for request correlation
- Host/pod/namespace metadata
- Integration with Grafana/Loki

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a PR.

## 📄 License

This project is licensed under the MIT License.

## 🏆 Project Highlights

- Implemented full CI/CD pipeline with automated image tagging
- Designed resilient microservices architecture
- Developed comprehensive logging and monitoring
- Containerized all components with security best practices
- Automated deployment with ArgoCD GitOps
