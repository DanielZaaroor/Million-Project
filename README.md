# Million-Project
Improving the counting flow of the group by checking for errors and missing numnbers.

## 1. Prequisites
As the working environment for the services, I used an always-free Oracle Ampre Ubuntu VM.
I created a network and subnet before, then the VM.
It will probably only be available with PAYGO account, but if configured right should stay free of cost.

With the new VM you can go to root and clone the repo:
```
sudo mkdir /million-project /million-project/wuzapi-data /million-project/rabbitmq_data
cd /million-project && 
git clone https://github.com/DanielZaaroor/Million-Project.git
touch .env
```
> env is not here obviously, figure it out.
## 2. Installations
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

Important Docker compose CLI commands: (you should have cloned the repo already)
```
docker-compose up -d --build
docker-compose logs --no-color -f wuzapi | less 
docker-compose down && docker-compose up -d
docker compose up -d --build --force-recreate logic_engine
```
For first build
To view logs of one service
Restart services
Restart specific service

### WuzAPI:
First, create a user:
```
curl -X POST http://localhost:8080/admin/users \
  -H "Authorization: my_secure_token_123" \
  -H "Content-Type: application/json" \
  -d '{"name": "MyBot", "token": "MyUserToken123"}'
```
Than create a session connection:
```
curl -X POST http://localhost:8080/session/connect \
  -H "Token: MyUserToken123" \
  -H "Content-Type: application/json" \
  -d '{"Subscribe":["Message","ReadReceipt"]}'

curl -s -H "Token: MyUserToken123" http://localhost:8080/session/qr
```
Now this will output a base64 image QR, you can eiter decode it from [This Site](https://base64.guru/converter/decode/image), or view the logs with the command from before.
Open your whatsapp app and go to connected devices. scan the QR, and voila, we got a new session!

To make our life easier, I created a script for the api calls, copy it from the repo to the path:
```
mv ./send_wuzapi /usr/local/bin/send_wuzapi
sudo chmod +x /usr/local/bin/send_wuzapi
send_wuzapi /chat/send/text -d '{"Phone": "972585011102", "Body": "Test Easier message!"}'
```

At this point I had a lot of trial and error with the code, so figured “why not make CI/CD for that part!”
Create Github self-hosted runner (linux, on actions settings). I forgot the machine is using ARM64 architecture, so choose that option on the install
After the install process (explanation on Github page), run this to create a service:
```
./svc.sh install && ./svc.sh start
``` 
In the repo, the workflow sits in file  - .github/workflows/deploy.yml
Now after connecting your IDE to github it's possible to commit and let the CI/CD do the magic!
