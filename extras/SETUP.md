# SETUP
This doc will try to describe the setup proccess of this project, outside the scope of the code itself

## 1. Prequisites
As the working environment for the services, I used an always-free Oracle Ampre Ubuntu VM.
I created a network and subnet before, then the VM.
It will probably only be available with PAYGO account, but if configured right should stay free of cost.

With the new VM you can go to root and clone the repo:
```
git clone https://github.com/DanielZaaroor/Million-Project.git
mkdir Million-Project//wuzapi-data Million-Project/rabbitmq_data
```
## 2. Installations & Configurations
### docker
```
sudo apt update && sudo apt upgrade -y
sudo apt install ca-certificates curl gnupg lsb-release -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```
**verify with:    docker run hello-world**
> To run docker commands without root, run this command then logout:     **sudo usermod -aG docker ${USER}**

Important Docker compose CLI commands:
```
docker-compose up -d --build
docker-compose logs --no-color -f wuzapi | less 
docker-compose down && docker-compose up -d
docker compose up -d --build --force-recreate logic_engine
```
(1) For first build |(2) To view logs of one service |(3) Restart all services |(4) Restart specific service

### WuzAPI - Whatsapp connection:
First, create a user (generate a random token and save it on .env):
```
curl -X POST http://localhost:8080/admin/users \
  -H "Authorization:adminToken" \
  -H "Content-Type: application/json" \
  -d '{"name": "MyBot", "token": "MyUserToken"}'
```
Than create a session connection:
```
curl -X POST http://localhost:8080/session/connect \
  -H "Token:adminToken" \
  -H "Content-Type: application/json" \
  -d '{"Subscribe":["Message"]}'

curl -s -H "Token:adminToken" http://localhost:8080/session/qr
```
Now this will output a base64 image QR, you can eiter decode it from [This Site](https://base64.guru/converter/decode/image), or view it in the wuzapi logs.
Open your whatsapp app and go to connected devices. scan the QR, and voila, we got a new session!
>The QR will be valid for less than a minute, be quick

To make our life easier, I created a [script for the api calls](../send_wuzapi), add your token then use this code:
```
mv ./send_wuzapi /usr/local/bin/send_wuzapi
sudo chmod +x /usr/local/bin/send_wuzapi
send_wuzapi /chat/send/text -d '{"Phone": "phoneNumberHere", "Body": "Test Easier message!"}'
```

### CI/CD (deploy code from repo to the VM)
Create Github self-hosted runner (linux, on actions settings). I forgot the machine is using ARM64 architecture, so choose that option on the install!
After the install process (explanation on Github page), run this to create a service:
```
./svc.sh install && ./svc.sh start
``` 
[playbook deploy file](../github/workflows/deploy.yml)
Now after connecting your IDE to github after each commit to the code dir, the containers will redeploy!

## 3. Common Bugs
### Connection to wuzapi refused
if the data stops comming and you recieve a 500 response code when trying to reconnect. try updating the image.
Sometimes Whatsapp changes protocol, and our wuzapi immage needs too be latest to match it.
