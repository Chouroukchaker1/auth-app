# k3s and Argo CD deployment

These manifests are a starter deployment for a single-node k3s server. The frontend is exposed on TCP port 30080; PostgreSQL data is stored in a 5 GiB persistent volume using k3s' default `local-path` storage class.

## 1. Install k3s

Run on the Linux server:

```sh
curl -sfL https://get.k3s.io | sh -
sudo kubectl get nodes
```

Allow inbound TCP port 30080 in the server firewall. The application will be available at `http://SERVER_IP:30080`.

## 2. Create the application secrets

Create the namespace and a Kubernetes Secret on the server. Do not commit these values to Git:

```sh
sudo kubectl create namespace auth-app
sudo kubectl -n auth-app create secret generic auth-app-secrets \
  --from-literal=POSTGRES_DB=authdb \
  --from-literal=POSTGRES_USER=authuser \
  --from-literal=POSTGRES_PASSWORD='CHANGE_ME_TO_A_STRONG_DATABASE_PASSWORD' \
  --from-literal=JWT_SECRET="$(openssl rand -base64 48)" \
  --from-literal=ADMIN_EMAIL='' \
  --from-literal=ADMIN_PASSWORD='' \
  --from-literal=MAIL_HOST='' \
  --from-literal=MAIL_USERNAME='' \
  --from-literal=MAIL_PASSWORD=''
```

Set `FRONTEND_URL` in `k8s/configmap.yaml` to `http://SERVER_IP:30080` before applying the Argo CD Application so emailed links use the public application address.

## 3. Install Argo CD

```sh
sudo kubectl create namespace argocd
sudo kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
sudo kubectl apply -f argocd/application.yaml
```

The Application tracks the GitHub repository's default branch and automatically applies changes under `k8s/`. To inspect Argo CD locally, run `sudo kubectl port-forward -n argocd svc/argocd-server 8082:443`; then open `https://localhost:8082`. The initial admin password is available with:

```sh
sudo kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
```

## 4. Deploy image updates

Jenkins currently publishes versioned images to Docker Hub but does not update Kubernetes manifests. After a successful image push, update the image tags in `k8s/backend.yaml` and/or `k8s/frontend.yaml` to the Jenkins build number and push that Git change; Argo CD will roll out the new version. Do not rely on re-pushing `latest` alone because Argo CD detects Git changes, not registry changes.

The NodePort setup is intended for initial testing. For an internet-facing production deployment, add a DNS name, HTTPS ingress, backups for the PostgreSQL volume, and a secret-management workflow.