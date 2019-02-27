# sat
visualize Sar data

# How to install sat with docker-compose
### Step 1
Copy `env.example` to `.env`. then replace `# GRAFANA_HOST=<hostname/IP without http>` by `GRAFANA_HOST=<yourhost ip>`
### Step 2
Run `docker-compose up --build -d`
### Step 3
Make sure all docker containers are `Up` with running `docker-compose ps`
  
# Usage
### Step 1
input URL `http://<your host ip>:8001/` in browser
### Step 2
user: admin password: admin
### Step 3
click `choose file`, upload sar data file(test/) then select graph type. then click `upload`. BTW: All types will be selected if `Check All` is set.
### Step 4
Click dashboard link URL to get your visualization dashboard (grafana user/passwd is admin/admin)

# Web Screenshots
![wait](https://raw.githubusercontent.com/zwg0106/sat/master/doc/sar-dashboard-screencapture.png)
