# lab-docker-ss
Dockerized version of Architecture for ASVs, SITL, MQTT, MAVPROXY

# Prerequisites
You must install a docker engine /docker desktop at your computer before moving forward.  [Docker Installation]( https://docs.docker.com/engine/install/)


# Setup 
Please create and fill out with appropriate values your environmnet  `.env` file (this should be located in the same directory your docker-compose.yml file is located)

```
GITHUB_TOKEN="SETUP YOUR GITHUB TOKEN HERE"
REPO_URL="SETUP YOUR REPO URL FOR COMPANION COMPUTER HERE"
BRANCH=main

# MQTT RELATED CONFIGURATION FOR LOCAL DEV Keep as is
MQTT_USERNAME=ss2026
MQTT_PASSWORD=ss2026
MQTT_BROKER=mosquitto
MQTT_PORT=1883

```

# Build Images 

``` bash
    docker-compose build 
```


# Initialize mosquitto 

Setup password for user 'ss2026'
```bash 
    docker-compose run --rm mosquitto mosquitto_passwd -c /mosquitto/config/mosquitto.passwd ss2026
    #if file already exists you can use this command
    #docker-compose run --rm mosquitto mosquitto_passwd  ss2026 (or whatever usename have selected)
```

Also **ss2026** 
You will be prompted to enter a password twice please make sure it matches the one you have define in  **MQTT_PASSWORD**

- Container swarm_env-mosquitto-run-787f07f18bac Creating 
- Container swarm_env-mosquitto-run-787f07f18bac Created 
- Password:  
- Reenter password: 
- Adding password for user ss2026


**If successful you shoule be able to locate password file at :/mosquitto/config/mosquitto.passwd**

# Spin up simulated images 
You can spin up all containers in docker-compose.yml using the following command. For interactive mode remove **-d** argument
```bash
    docker-compose up -d 
```

## Rebuild everything from scratch
```bash
    docker compose down; docker-compose build --no-cache ; docker-compose up -d     
```
# connect to QgroundControl

You may interact with SITL inside the containers using [QgroundControl](https://qgroundcontrol.com/)
- At startup need to manually connect to **mavcontrol**. Go Click to manually connect  and select  **mavcontrol**
- After that you should be able to have full control of the corresponding ASVs inside the containers through this application.
- 

