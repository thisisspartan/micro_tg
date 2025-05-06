# My Favorite Movie Poster Telegram Bot (Kubernetes Deployment)

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
flowchart TD
    subgraph External ["External Services"]
        TMDB["TMDB API"]
        TG["Telegram API"]
        style External fill:transparent,stroke-dasharray: 5 5
    end

    subgraph Infrastructure ["Kubernetes Cluster"]
        style Infrastructure fill:transparent,stroke-dasharray: 5 5
        subgraph Services ["Application Services"]
            TMDB_SVC["TMDB Service\n(Python 3.10)"]
            TG_BOT["Telegram Bot\n(Python 3.10)"]
            SSH["SSH Tunnel\n(SOCKS5 Proxy)"]
        end
        
        subgraph Storage ["Data Storage"]
            REDIS["Redis\n(Queue + Metadata)"]
        end
        
        subgraph Observability ["Monitoring Stack"]
            PROMTAIL["Promtail\n(Log Collection)"]
            LOKI["Loki\n(Log Storage)"]
            GRAFANA["Grafana\n(Visualization)"]
        end
        
        subgraph CI_CD ["CI/CD Pipeline"]
            GITEA["Gitea\n(Source Repo)"]
            ARGOCD["ArgoCD\n(GitOps Sync)"]
        end
    end
    
    %% Data Flow Connections
    TMDB -->|API Requests| SSH
    SSH -->|Secured Connection| TMDB_SVC
    TMDB_SVC -->|Store Movie Data| REDIS
    REDIS -->|Fetch Poster Queue| TG_BOT
    TG_BOT -->|Publish Posters| TG
    
    %% Logging Flow
    TMDB_SVC -->|Structured Logs| PROMTAIL
    TG_BOT -->|Structured Logs| PROMTAIL
    SSH -->|Logs| PROMTAIL
    PROMTAIL -->|Forward| LOKI
    LOKI -->|Visualize| GRAFANA
    
    %% Deployment Flow
    GITEA -->|Manifests| ARGOCD
    ARGOCD -->|Deploy| Infrastructure

    classDef primary fill:#4286f4,stroke:#0f5edb,color:white,stroke-width:2px
    classDef storage fill:#f9a825,stroke:#c17900,color:white,stroke-width:2px
    classDef monitoring fill:#43a047,stroke:#00701a,color:white,stroke-width:2px
    classDef cicd fill:#8e24aa,stroke:#5c007a,color:white,stroke-width:2px
    classDef external fill:#78909c,stroke:#4b636e,color:white,stroke-width:2px

    class TMDB_SVC,TG_BOT,SSH primary
    class REDIS storage
    class PROMTAIL,LOKI,GRAFANA monitoring
    class GITEA,ARGOCD cicd
    class TMDB,TG external
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
